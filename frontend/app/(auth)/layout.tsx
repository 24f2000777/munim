export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-cream flex items-center justify-center p-4">
      {/* Decorative background */}
      <div className="fixed inset-0 pointer-events-none overflow-hidden">
        <div className="absolute top-0 right-0 w-[600px] h-[600px] bg-saffron/6 rounded-full blur-3xl -translate-y-1/2 translate-x-1/4" />
        <div className="absolute bottom-0 left-0 w-[400px] h-[400px] bg-forest/5 rounded-full blur-3xl translate-y-1/3 -translate-x-1/4" />
      </div>
      <div className="relative z-10 w-full">{children}</div>
    </div>
  );
}
