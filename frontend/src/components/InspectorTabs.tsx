import type { KeyboardEvent, ReactNode } from "react";

export interface InspectorTabSpec<T extends string> {
  id: T;
  label: string;
  count?: number;
  content: ReactNode;
}

interface InspectorTabsProps<T extends string> {
  tabs: InspectorTabSpec<T>[];
  activeTab: T;
  onChange: (tab: T) => void;
}

export function InspectorTabs<T extends string>({
  tabs,
  activeTab,
  onChange,
}: InspectorTabsProps<T>) {
  const activeIndex = tabs.findIndex((tab) => tab.id === activeTab);
  const active = tabs[activeIndex] ?? tabs[0];

  if (!active) {
    return null;
  }

  function moveTo(index: number) {
    const nextTab = tabs[index];

    if (!nextTab) {
      return;
    }

    onChange(nextTab.id);
    if (typeof window !== "undefined" && typeof document !== "undefined") {
      window.requestAnimationFrame(() => {
        document.getElementById(`inspector-tab-${nextTab.id}`)?.focus();
      });
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!tabs.length) {
      return;
    }

    switch (event.key) {
      case "ArrowRight":
      case "ArrowDown":
        event.preventDefault();
        moveTo((index + 1) % tabs.length);
        break;
      case "ArrowLeft":
      case "ArrowUp":
        event.preventDefault();
        moveTo((index - 1 + tabs.length) % tabs.length);
        break;
      case "Home":
        event.preventDefault();
        moveTo(0);
        break;
      case "End":
        event.preventDefault();
        moveTo(tabs.length - 1);
        break;
      default:
        break;
    }
  }

  return (
    <div className="inspector-shell">
      <div className="tab-strip" role="tablist" aria-label="Inspector views" aria-orientation="horizontal">
        {tabs.map((tab, index) => {
          const selected = tab.id === activeTab;

          return (
            <button
              key={tab.id}
              id={`inspector-tab-${tab.id}`}
              type="button"
              role="tab"
              aria-selected={selected}
              aria-controls={`inspector-panel-${tab.id}`}
              tabIndex={selected ? 0 : -1}
              className={`tab-strip__button${selected ? " is-active" : ""}`}
              onClick={() => onChange(tab.id)}
              onKeyDown={(event) => handleKeyDown(event, index)}
            >
              <span>{tab.label}</span>
              {typeof tab.count === "number" ? (
                <span className="tab-strip__count">{tab.count}</span>
              ) : null}
            </button>
          );
        })}
      </div>
      <div
        id={`inspector-panel-${active.id}`}
        className="tab-panel"
        role="tabpanel"
        aria-labelledby={`inspector-tab-${active.id}`}
      >
        {active.content}
      </div>
    </div>
  );
}
