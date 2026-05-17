export type UserRole       = "User" | "Admin" | "SuperAdmin" | "Manager" | "Viewer";
export type UserVerified   = "Verified" | "Unverified";
export type UserFilterTab  = "All" | "Verified" | "Unverified";

export interface User {
  id:        string;
  sn:        number;
  firstName: string;
  lastName:  string;
  email:     string;
  role:      UserRole;
  verified:  UserVerified;
  createdAt: string;
}
