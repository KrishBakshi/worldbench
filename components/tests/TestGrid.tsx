import { getAllTests } from "@/lib/tests";
import { getProvider } from "@/lib/providers";
import TestBrowser, { type ProviderOption } from "@/components/tests/TestBrowser";

export default function TestGrid() {
  const tests = getAllTests();

  // One badge per provider that actually has a test, in first-seen order
  // (tests come pre-sorted newest first).
  const providers: ProviderOption[] = [];
  const seen = new Set<string>();
  for (const test of tests) {
    if (!test.provider || seen.has(test.provider)) continue;
    const provider = getProvider(test.provider);
    if (!provider) continue;
    seen.add(test.provider);
    providers.push({ slug: test.provider, name: provider.name });
  }

  return <TestBrowser tests={tests} providers={providers} />;
}
