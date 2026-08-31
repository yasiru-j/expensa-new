// Two letters from the full name if set ("Yasiru Jayasinghe" -> "YJ"),
// else the first two letters of the email's local part as a fallback —
// full_name is optional (see AccountPage), so this always has something
// to show in the avatar circle.
export function initialsFor(fullName: string | null, email: string): string {
  if (fullName && fullName.trim()) {
    const parts = fullName.trim().split(/\s+/);
    const first = parts[0]?.[0] ?? "";
    const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? "") : "";
    const initials = (first + last).toUpperCase();
    if (initials) return initials;
  }
  return email.slice(0, 2).toUpperCase();
}

export function firstNameFor(fullName: string | null, email: string): string {
  if (fullName && fullName.trim()) return fullName.trim().split(/\s+/)[0];
  return email.split("@")[0];
}
