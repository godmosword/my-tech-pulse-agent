import { PageSkeleton } from "@/components/data/PageSkeleton";

/**
 * Suspense fallback for the (app) main content column during server-component
 * data loading. Renders inside the existing layout's <main> — no app chrome.
 */
export default function Loading() {
  return <PageSkeleton />;
}
