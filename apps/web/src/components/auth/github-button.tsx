"use client";

import { useQuery } from "@tanstack/react-query";
import { Github } from "lucide-react";

import { Button } from "@/components/ui/button";
import { githubConfig, startGitHubAuth } from "@/lib/auth";

export function GitHubButton({ label }: { label: string }) {
  const { data } = useQuery({
    queryKey: ["github-config"],
    queryFn: githubConfig,
    staleTime: 10 * 60 * 1000,
  });
  const configured = data?.configured ?? false;

  return (
    <div className="mt-6">
      <Button
        type="button"
        variant="outline"
        className="h-12 w-full"
        disabled={!configured}
        onClick={() => configured && data && startGitHubAuth(data.client_id)}
      >
        <Github className="mr-2 size-5" />
        {label}
      </Button>
      {!configured && (
        <p className="mt-2 text-center text-xs text-muted-foreground">GitHub 登录即将开放</p>
      )}
    </div>
  );
}
