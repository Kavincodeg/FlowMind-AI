import React from 'react';

export interface LoadingStateProps {
  message?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

export const LoadingState: React.FC<LoadingStateProps> = ({
  message = 'Loading...',
  size = 'md',
  className = '',
}) => {
  return (
    <div className={`loading-state ${className}`.trim()} role="status" aria-live="polite">
      <span className={`loading-spinner spinner-${size}`} aria-hidden="true" />
      {message && <p className="loading-message">{message}</p>}
    </div>
  );
};
