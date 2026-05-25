import { avatarUrl, type AuthUser } from "@/lib/auth";
import { cn } from "@/lib/utils";

interface AvatarProps {
  user: Pick<AuthUser, "name" | "email" | "avatar">;
  className?: string;
}

/** 用户头像：有图显示图，否则显示首字母渐变圆。 */
export function Avatar({ user, className }: AvatarProps) {
  const url = avatarUrl(user);
  const initial = (user.name || user.email).charAt(0).toUpperCase();

  return (
    <span
      className={cn(
        "flex shrink-0 items-center justify-center overflow-hidden rounded-full bg-gradient-to-br from-violet-500 to-fuchsia-500 font-semibold text-white",
        className,
      )}
    >
      {url ? (
        // eslint-disable-next-line @next/next/no-img-element
        <img src={url} alt={user.name || user.email} className="size-full object-cover" />
      ) : (
        initial
      )}
    </span>
  );
}
