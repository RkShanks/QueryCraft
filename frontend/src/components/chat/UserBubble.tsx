import React from 'react';
import './UserBubble.css';

interface UserBubbleProps {
  text: string;
}

export const UserBubble: React.FC<UserBubbleProps> = ({ text }) => {
  return (
    <div className="user-bubble-wrapper" data-testid="user-bubble">
      <div className="user-bubble">
        <p className="user-bubble-text">{text}</p>
      </div>
    </div>
  );
};
