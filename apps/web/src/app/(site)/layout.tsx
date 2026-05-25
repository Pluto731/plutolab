import { BackgroundOrbs } from "@/components/background-orbs";
import { CommandPalette } from "@/components/command-palette";
import { Nav } from "@/components/nav";
import { PageTransition } from "@/components/page-transition";
import { ScrollProgress } from "@/components/scroll-progress";

export default function SiteLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <>
      <BackgroundOrbs />
      <ScrollProgress />
      <Nav />
      <CommandPalette />
      <PageTransition>{children}</PageTransition>
    </>
  );
}
