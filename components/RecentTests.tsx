import { getPinnedTests } from "@/lib/tests";
import TestCard from "@/components/TestCard";

export default function RecentTests() {
  const tests = getPinnedTests(4);
  if (tests.length === 0) return null;

  return (
    <section className="mx-auto w-full max-w-5xl shrink-0 px-6 pb-6 md:px-10">
      <h2 className="mb-3 text-xs uppercase tracking-[0.2em] text-mist">
        See Recent Tests
      </h2>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {tests.map((test) => (
          <TestCard key={test.slug} test={test} compact />
        ))}
      </div>
    </section>
  );
}
