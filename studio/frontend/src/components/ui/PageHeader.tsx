import React from "react";

export interface PageHeaderProps {
  title: string;
  breadcrumb?: Array<{ label: string; href?: string; onClick?: () => void }>;
  actions?: React.ReactNode;
  description?: string;
}

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  breadcrumb,
  actions,
  description,
}) => {
  return (
    <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 pb-6 border-b border-edge/40 mb-6">
      <div className="space-y-1">
        {breadcrumb && breadcrumb.length > 0 && (
          <nav className="flex items-center gap-1.5 text-xs text-text-muted mb-1">
            {breadcrumb.map((crumb, idx) => (
              <React.Fragment key={idx}>
                {idx > 0 && <span>/</span>}
                {crumb.onClick ? (
                  <button
                    onClick={crumb.onClick}
                    className="hover:text-white transition-colors cursor-pointer"
                  >
                    {crumb.label}
                  </button>
                ) : crumb.href ? (
                  <a href={crumb.href} className="hover:text-white transition-colors">
                    {crumb.label}
                  </a>
                ) : (
                  <span className="text-slate-400 font-medium">{crumb.label}</span>
                )}
              </React.Fragment>
            ))}
          </nav>
        )}
        <h1 className="text-xl font-bold tracking-tight text-white">{title}</h1>
        {description && <p className="text-xs text-text-muted">{description}</p>}
      </div>
      {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
    </div>
  );
};
