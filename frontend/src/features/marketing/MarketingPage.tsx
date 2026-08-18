import { MarketingNav } from "./components/MarketingNav";
import { HeroSection } from "./components/HeroSection";
import { TechMarquee } from "./components/TechMarquee";
import { HowItWorks } from "./components/HowItWorks";
import { IntegratedPlatform } from "./components/IntegratedPlatform";
import { FeatureGrid } from "./components/FeatureGrid";
import { SeverityLadder } from "./components/SeverityLadder";
import { HospitalAnalogy } from "./components/HospitalAnalogy";
import { ProductShowcase } from "./components/ProductShowcase";
import { IntegrationsSection } from "./components/IntegrationsSection";
import { ResearchComponents } from "./components/ResearchComponents";
import { CtaBand } from "./components/CtaBand";
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
        <TechMarquee />
        <HowItWorks />
        <IntegratedPlatform />
        <FeatureGrid />
        <SeverityLadder />
        <HospitalAnalogy />
        <ProductShowcase />
        <IntegrationsSection />
        <ResearchComponents />
        <CtaBand />
      </main>
      <MarketingFooter />
    </div>
  );
}
