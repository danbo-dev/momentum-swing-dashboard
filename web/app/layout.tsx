import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Momentum-Swing Dashboard",
  description: "Momentum + catalysts, quality-gated. Multi-week swing signals.",
};

// Set the theme attribute before paint to avoid a flash.
const themeScript = `(function(){try{var m=localStorage.getItem('theme');if(m&&m!=='system')document.documentElement.setAttribute('data-theme',m);}catch(e){}})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
      </head>
      <body>{children}</body>
    </html>
  );
}
