import React from 'react';

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: 'default' | 'elevated' | 'interactive';
  header?: React.ReactNode;
  footer?: React.ReactNode;
}

export const Card: React.FC<CardProps> = ({
  variant = 'default',
  header,
  footer,
  children,
  className = '',
  ...props
}) => {
  const variantClass = variant === 'elevated' ? 'card-elevated' : variant === 'interactive' ? 'card-interactive' : '';
  return (
    <div className={`card ${variantClass} ${className}`.trim()} {...props}>
      {header && <div className="card-header">{header}</div>}
      <div className="card-body">{children}</div>
      {footer && <div className="card-footer">{footer}</div>}
    </div>
  );
};
