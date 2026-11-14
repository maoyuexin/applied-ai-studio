import {
  Blocks,
  Building2,
  Factory,
  Film,
  GraduationCap,
  HardHat,
  HeartPulse,
  Landmark,
  Link2,
  ScanSearch,
  ShieldAlert,
  ShoppingBag,
  Wallet,
  Waves,
  type LucideIcon,
} from "lucide-react";

const iconMap: Record<string, LucideIcon> = {
  blocks: Blocks,
  "building-2": Building2,
  clapperboard: Film,
  factory: Factory,
  film: Film,
  "graduation-cap": GraduationCap,
  "hard-hat": HardHat,
  "heart-pulse": HeartPulse,
  landmark: Landmark,
  "link-2": Link2,
  "scan-search": ScanSearch,
  "shield-alert": ShieldAlert,
  "shopping-bag": ShoppingBag,
  wallet: Wallet,
  waves: Waves,
};

export default function IndustryIcon({ name, size = 20 }: { name: string; size?: number }) {
  const Icon = iconMap[name] ?? Building2;
  return <Icon size={size} aria-hidden="true" />;
}