import React from 'react';
import { Badge } from "@/components/ui/badge";

interface Metric {
    label: string;
    score: number; // 1-5
    text: string;
}

interface DynamicTasteChartProps {
    categoryName: string;
    metrics: Metric[];
}

export default function DynamicTasteChart({ categoryName, metrics }: DynamicTasteChartProps) {
    return (
        <div className="space-y-5 animate-in fade-in slide-in-from-bottom-2 duration-700">
            <div className="flex items-center justify-between">
                <h4 className="text-[10px] font-black text-slate-400 uppercase tracking-widest">Dynamic Taste Analysis</h4>
                <Badge variant="outline" className="text-[9px] font-black border-slate-200 text-slate-500 rounded-lg px-2 py-0.5">
                    {categoryName || "분석중"}
                </Badge>
            </div>

            <div className="grid gap-5">
                {metrics?.map((metric, idx) => (
                    <div key={idx} className="space-y-2">
                        <div className="flex justify-between items-end px-0.5">
                            <span className="text-[13px] font-black text-slate-700 tracking-tight">
                                {metric.label}
                            </span>
                            <span className="text-[10px] font-bold text-slate-400">
                                {metric.score} / 5
                            </span>
                        </div>

                        <div className="relative h-2.5 w-full overflow-hidden rounded-full bg-slate-100 border border-slate-50/50">
                            <div
                                className="h-full bg-slate-900 transition-all duration-1000 ease-out rounded-full"
                                style={{ width: `${(metric.score / 5) * 100}%` }}
                            />
                        </div>

                        <p className="text-[11px] font-medium text-slate-500 leading-relaxed pl-0.5 opacity-80">
                            {metric.text}
                        </p>
                    </div>
                ))}
            </div>
        </div>
    );
}

// Simple internal progress component for convenience if the UI one isn't imported
// In a real shadcn setup we'd use @/components/ui/progress
