import Link from "next/link";
import { Home } from "lucide-react";

export default function NotFound() {
  return (
    <div className="min-h-screen bg-cream flex items-center justify-center p-4 text-center">
      <div>
        <div className="w-16 h-16 rounded-2xl bg-saffron/10 flex items-center justify-center mx-auto mb-5">
          <span className="text-3xl">🔍</span>
        </div>
        <h1 className="text-3xl font-black text-forest mb-2">404</h1>
        <p className="font-semibold text-forest text-lg mb-1">Yeh page nahi mila</p>
        <p className="text-sm text-muted-foreground mb-6">
          Aap galat page pe aa gaye ho. Wapas jaao!
        </p>
        <Link
          href="/"
          className="inline-flex items-center gap-2 bg-saffron hover:bg-saffron-dark text-white font-semibold px-6 py-2.5 rounded-xl shadow-warm transition-all"
        >
          <Home className="w-4 h-4" />
          Ghar jaao
        </Link>
      </div>
    </div>
  );
}
