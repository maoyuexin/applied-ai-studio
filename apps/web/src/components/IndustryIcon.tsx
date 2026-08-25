import {
  Building2,
  Factory,
  GraduationCap,
  HardHat,
  HeartPulse,
  Landmark,
  ShieldAlert,
  ShoppingBag,
  Waves,
  type LucideIcon,
} from "lucide-react";

const iconMap: Record<string, LucideIcon> = {
  "building-2": Building2,
  factory: Factory,
  "graduation-cap": GraduationCap,
  "hard-hat": HardHat,
  "heart-pulse": HeartPulse,
  landmark: Landmark,
  "shield-alert": ShieldAlert,
  "shopping-bag": ShoppingBag,
  waves: Waves,
};

export default function IndustryIcon({ name, size = 20 }: { name: string; size?: number }) {
  const Icon = iconMap[name] ?? Building2;
  return <Icon size={size} aria-hidden="true" />;
}