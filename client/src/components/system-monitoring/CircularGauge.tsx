"use client";

import React from "react";

interface CircularGaugeProps {
  value:  number;   // 0–100
  size?:  number;   // px, default 120
  stroke?: number;  // stroke width, default 10
  label:  string;
}

/** Returns a Tailwind-compatible hex colour based on the value */
function gaugeColor(value: number): string {
  if (value < 50) return "#166534";  // success-500
  if (value < 75) return "#F59E0B";  // amber-400 — warning
  return "#E31E24";                  // error-500
}

export function CircularGauge({ value, size = 120, stroke = 10, label }: CircularGaugeProps) {
  const radius      = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const offset      = circumference - (value / 100) * circumference;
  const color       = gaugeColor(value);

  return (
    <div className="flex flex-col items-center gap-2">
      <div className="relative" style={{ width: size, height: size }}>
        <svg width={size} height={size} className="-rotate-90">
          {/* Track */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth={stroke}
            className="text-gray-100 dark:text-gray-800"
          />
          {/* Progress */}
          <circle
            cx={size / 2}
            cy={size / 2}
            r={radius}
            fill="none"
            stroke={color}
            strokeWidth={stroke}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
            strokeLinecap="round"
            style={{ transition: "stroke-dashoffset 0.6s ease" }}
          />
        </svg>
        {/* Centre label */}
        <div className="absolute inset-0 flex items-center justify-center">
          <span
            className="text-base font-semibold"
            style={{ color }}
          >
            {value}%
          </span>
        </div>
      </div>
      <span className="text-theme-xs text-gray-500 dark:text-gray-400">{label}</span>
    </div>
  );
}