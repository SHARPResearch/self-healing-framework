import { MarketingNav } from "./components/MarketingNav";
import { HeroSection } from "./components/HeroSection";
import { HowItWorks } from "./components/HowItWorks";
import { HospitalAnalogy } from "./components/HospitalAnalogy";
import { SeverityLadder } from "./components/SeverityLadder";
import { ProductShowcase } from "./components/ProductShowcase";
import { ResearchComponents } from "./components/ResearchComponents";
import { TechStack } from "./components/TechStack";
import { MarketingFooter } from "./components/MarketingFooter";

/**
 * Public landing page. Deliberately not wrapped in AppShell -- it owns its own
 * nav and footer, and is the only route outside the authenticated shell.
 */
export function MarketingPage() {
  return (
    <div className="min-h-screen scroll-smooth bg-black text-white">
      <MarketingNav />
      <main>
        <HeroSection />
        <HowItWorks />
        <HospitalAnalogy />
        <SeverityLadder />
        <ProductShowcase />
        <ResearchComponents />
        <TechStack />
      </main>
      <MarketingFooter />
    </div>
  );
}
