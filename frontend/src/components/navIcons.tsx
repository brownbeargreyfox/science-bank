import {
  ClipboardTaskListLtr24Filled,
  ClipboardTaskListLtr24Regular,
  Beaker24Filled,
  Beaker24Regular,
  Box24Filled,
  Box24Regular,
  DataBarVertical24Filled,
  DataBarVertical24Regular,
  Database24Filled,
  Database24Regular,
  Home24Filled,
  Home24Regular,
  Library24Filled,
  Library24Regular,
  Settings24Filled,
  Settings24Regular,
  TableSimple24Filled,
  TableSimple24Regular,
  type FluentIcon,
} from "@fluentui/react-icons";

/**
 * Navigation icons, one place. They come from Microsoft's Fluent System Icons (MIT). Regular is the resting
 * state; Filled marks the page you are on. If the full icon package is later trimmed or vendored, only this
 * file changes.
 */
export const NAV_ICONS: Record<
  string,
  { regular: FluentIcon; filled: FluentIcon }
> = {
  "/": { regular: Home24Regular, filled: Home24Filled },
  "/standards": { regular: Library24Regular, filled: Library24Filled },
  "/bundles": { regular: Box24Regular, filled: Box24Filled },
  "/coverage": { regular: TableSimple24Regular, filled: TableSimple24Filled },
  "/generate": { regular: Beaker24Regular, filled: Beaker24Filled },
  "/questions": { regular: Database24Regular, filled: Database24Filled },
  "/assessments": {
    regular: ClipboardTaskListLtr24Regular,
    filled: ClipboardTaskListLtr24Filled,
  },
  "/results": {
    regular: DataBarVertical24Regular,
    filled: DataBarVertical24Filled,
  },
  "/admin/users": { regular: Settings24Regular, filled: Settings24Filled },
};
