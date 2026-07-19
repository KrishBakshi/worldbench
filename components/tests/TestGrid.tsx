import { getAllTests } from "@/lib/tests";
import TestCard from "@/components/TestCard";

export default function TestGrid() {
  const tests = getAllTests();

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {tests.map((test) => (
        <TestCard key={test.slug} test={test} />
      ))}
    </div>
  );
}
