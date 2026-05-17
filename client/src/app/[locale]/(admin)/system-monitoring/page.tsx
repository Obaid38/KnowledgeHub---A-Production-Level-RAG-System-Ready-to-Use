import SystemMonitoring from "@/components/system-monitoring";
import { Metadata } from "next";

export const metadata: Metadata = {
  title: "System Monitoring | Dashboard",
  description: "Monitor system performance and health.",
};
export default function SystemMonitoringPage() {
  return <SystemMonitoring />;
}