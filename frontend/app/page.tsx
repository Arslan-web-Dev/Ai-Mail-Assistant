import Link from "next/link";

export default function HomePage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center px-6 text-center">
      <h1 className="text-4xl font-bold tracking-tight text-slate-900">
        AI Mail Assistant
      </h1>
      <p className="mt-4 max-w-md text-slate-600">
        Connect Gmail, let AI understand every email, and review or auto-send
        professional replies — safely, and only for the emails that need one.
      </p>
      <Link
        href="/login"
        className="mt-8 rounded-lg bg-brand-600 px-6 py-3 text-sm font-medium text-white transition hover:bg-brand-700"
      >
        Get started
      </Link>
    </main>
  );
}
