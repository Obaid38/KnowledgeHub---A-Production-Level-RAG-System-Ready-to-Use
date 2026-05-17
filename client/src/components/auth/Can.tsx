"use client";

import type { ReactNode } from "react";
import { usePermission } from "@/hooks/usePermission";
import type { PermissionAction } from "@/types/roles.types";

interface CanProps {
  /**
   * The CRUD action(s) to gate.
   * Pass a single action or an array — with an array the content is rendered
   * if the user has **any** of the listed actions (canAny semantics).
   */
  action: PermissionAction | PermissionAction[];
  /**
   * Resource key mapped to the permission matrix.
   * Supported values: "document", "qa", "users", "system".
   * Pass any raw permission-row id (e.g. "doc") as a fallback.
   */
  resource: string;
  /** Content rendered when the user has the requested permission. */
  children: ReactNode;
  /**
   * Content rendered when the user lacks permission.
   * Defaults to `null` (nothing rendered).
   */
  fallback?: ReactNode;
}

/**
 * Can — declarative permission gate.
 *
 * Renders `children` when the current user holds the requested permission,
 * otherwise renders `fallback` (default: nothing).
 *
 * @example
 * // Hide upload zone for users without create:document permission
 * <Can action="create" resource="document">
 *   <UploadZone ... />
 * </Can>
 *
 * @example
 * // Show checkbox only if user can edit OR delete
 * <Can action={["edit", "delete"]} resource="document">
 *   <input type="checkbox" ... />
 * </Can>
 */
export function Can({ action, resource, children, fallback = null }: CanProps) {
  const { can, canAny } = usePermission();

  const allowed = Array.isArray(action)
    ? canAny(action, resource)
    : can(action, resource);

  return <>{allowed ? children : fallback}</>;
}
