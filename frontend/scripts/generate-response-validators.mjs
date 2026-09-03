import Ajv2020 from 'ajv/dist/2020.js';
import addFormats from 'ajv-formats';
import standaloneCode from 'ajv/dist/standalone/index.js';

export const UNION_VALIDATOR_ID = 'x-querycraft-union-validator';

function componentName(reference) {
  const prefix = '#/components/schemas/';
  return typeof reference === 'string' && reference.startsWith(prefix)
    ? reference.slice(prefix.length)
    : undefined;
}

function collectComponentNames(schema, componentNames) {
  if (Array.isArray(schema)) {
    for (const entry of schema) collectComponentNames(entry, componentNames);
    return;
  }
  if (!schema || typeof schema !== 'object') return;
  const referencedName = componentName(schema.$ref);
  if (referencedName) componentNames.add(referencedName);
  for (const nestedSchema of Object.values(schema)) {
    collectComponentNames(nestedSchema, componentNames);
  }
}

function reachableComponentSchemas(openapi, manifest) {
  const canonicalComponents = openapi.components?.schemas ?? {};
  const reachableNames = new Set();
  for (const operation of manifest) {
    for (const response of operation.responses) {
      collectComponentNames(response.schema, reachableNames);
    }
  }

  const pendingNames = [...reachableNames].sort();
  for (let index = 0; index < pendingNames.length; index += 1) {
    const component = pendingNames[index];
    const schema = canonicalComponents[component];
    if (!schema) throw new Error(`Response schema references absent component: ${component}`);
    const nestedNames = new Set();
    collectComponentNames(schema, nestedNames);
    for (const nestedName of [...nestedNames].sort()) {
      if (!reachableNames.has(nestedName)) {
        reachableNames.add(nestedName);
        pendingNames.push(nestedName);
      }
    }
  }

  return Object.fromEntries(
    [...reachableNames].sort().map((name) => [name, canonicalComponents[name]])
  );
}

function validationComponentId(name) {
  return `urn:querycraft:component:${encodeURIComponent(name)}`;
}

function absoluteValidationReferences(schema) {
  if (Array.isArray(schema)) return schema.map(absoluteValidationReferences);
  if (!schema || typeof schema !== 'object') return schema;
  return Object.fromEntries(
    Object.entries(schema).map(([key, nestedSchema]) => {
      if (key === '$ref') {
        const name = componentName(nestedSchema);
        return [key, name ? validationComponentId(name) : nestedSchema];
      }
      return [key, absoluteValidationReferences(nestedSchema)];
    })
  );
}

function annotateUnions(schema, unionDefinitions) {
  if (Array.isArray(schema)) {
    return schema.map((entry) => annotateUnions(entry, unionDefinitions));
  }
  if (!schema || typeof schema !== 'object') return schema;

  const alternatives = schema.anyOf ?? schema.oneOf;
  const unionId = Array.isArray(alternatives)
    ? `union_${String(unionDefinitions.length).padStart(4, '0')}`
    : undefined;
  if (unionId) unionDefinitions.push({ alternatives, id: unionId });

  const annotated = Object.fromEntries(
    Object.entries(schema).map(([key, nestedSchema]) => [
      key,
      annotateUnions(nestedSchema, unionDefinitions),
    ])
  );
  if (unionId) annotated[UNION_VALIDATOR_ID] = unionId;
  return annotated;
}

function annotatedSanitizationModel(manifest, componentSchemas) {
  const unionDefinitions = [];
  const annotatedManifest = manifest.map((operation) => ({
    ...operation,
    responses: operation.responses.map((response) => ({
      ...response,
      schema: annotateUnions(response.schema, unionDefinitions),
    })),
  }));
  const annotatedComponents = Object.fromEntries(
    Object.entries(componentSchemas).map(([name, schema]) => [
      name,
      annotateUnions(schema, unionDefinitions),
    ])
  );
  return { annotatedComponents, annotatedManifest, unionDefinitions };
}

function schemaCompiler(componentSchemas) {
  const compiler = new Ajv2020({
    allErrors: false,
    coerceTypes: false,
    code: { esm: true, optimize: true, source: true },
    strict: false,
    useDefaults: false,
  });
  addFormats(compiler);
  for (const [name, schema] of Object.entries(componentSchemas)) {
    compiler.addSchema(absoluteValidationReferences(schema), validationComponentId(name));
  }
  return compiler;
}

function validatorRegistry(compiler) {
  const exportBySchema = new Map();
  const schemaIdByExport = {};
  const register = (schema) => {
    const canonicalSchema = JSON.stringify(schema);
    const existingExport = exportBySchema.get(canonicalSchema);
    if (existingExport) return existingExport;
    const index = exportBySchema.size;
    const exportName = `validator_${String(index).padStart(4, '0')}`;
    const schemaId = `urn:querycraft:response-validator:${index}`;
    compiler.addSchema(absoluteValidationReferences(schema), schemaId);
    exportBySchema.set(canonicalSchema, exportName);
    schemaIdByExport[exportName] = schemaId;
    return exportName;
  };
  return { register, schemaIdByExport };
}

function responseValidatorExports(manifest, register) {
  const validators = {};
  for (const operation of manifest) {
    for (const response of operation.responses) {
      if (!response.schema) continue;
      validators[`${operation.operationId}:${response.status}`] = register(response.schema);
    }
  }
  return validators;
}

function unionValidatorExports(unionDefinitions, register) {
  return Object.fromEntries(
    unionDefinitions.map(({ alternatives, id }) => [
      id,
      alternatives.map((alternative) => register(alternative)),
    ])
  );
}

function staticEsmImports(source) {
  const imports = new Map();
  let normalized = source.replace(
    /const (\w+) = require\("([^"]+)"\)\.default;/g,
    (_binding, localName, moduleName) => {
      imports.set(`${moduleName}:default`, `import ${localName} from '${moduleName}';`);
      return '';
    }
  );
  if (normalized.includes('require("ajv-formats/dist/formats").fullFormats')) {
    imports.set(
      'ajv-formats:fullFormats',
      "import { fullFormats as querycraftFullFormats } from 'ajv-formats/dist/formats.js';"
    );
    normalized = normalized.replaceAll(
      'require("ajv-formats/dist/formats").fullFormats',
      'querycraftFullFormats'
    );
  }
  const importSource = [...imports.values()].sort().join('\n');
  return `${importSource}\n${normalized}`;
}

function mapSource(exportName, validators) {
  const entries = Object.entries(validators).map(
    ([key, validator]) => `  ${JSON.stringify(key)}: ${validator},`
  );
  return `export const ${exportName}: Readonly<Record<string, StandaloneResponseValidator>> = {\n${entries.join('\n')}\n};`;
}

function unionMapSource(validators) {
  const entries = Object.entries(validators).map(
    ([key, alternatives]) => `  ${JSON.stringify(key)}: [${alternatives.join(', ')}],`
  );
  return `export const unionAlternativeValidatorsById: Readonly<Record<string, readonly StandaloneResponseValidator[]>> = {\n${entries.join('\n')}\n};`;
}

function validatorSource(compiler, schemaIds, responseValidators, unionValidators) {
  const standalone = staticEsmImports(standaloneCode(compiler, schemaIds));
  const source = [
    '// @ts-nocheck -- generated AJV standalone validation code.',
    '// This file is auto-generated from backend/openapi.json.',
    standalone,
    'export type StandaloneResponseValidator = (response: unknown) => boolean;',
    mapSource('responseValidatorByOperationStatus', responseValidators),
    unionMapSource(unionValidators),
  ].join('\n\n') + '\n';
  if (/\brequire\s*\(|\bnew Function\b|\beval\s*\(/.test(source)) {
    throw new Error('Generated response validators contain dynamic or CommonJS code');
  }
  return source;
}

export function generateResponseValidationArtifacts(openapi, manifest) {
  const components = reachableComponentSchemas(openapi, manifest);
  const { annotatedComponents, annotatedManifest, unionDefinitions } =
    annotatedSanitizationModel(manifest, components);
  const compiler = schemaCompiler(components);
  const { register, schemaIdByExport } = validatorRegistry(compiler);
  const responseValidators = responseValidatorExports(manifest, register);
  const unionValidators = unionValidatorExports(unionDefinitions, register);
  return {
    componentSchemas: annotatedComponents,
    manifest: annotatedManifest,
    validatorSource: validatorSource(
      compiler,
      schemaIdByExport,
      responseValidators,
      unionValidators
    ),
  };
}
