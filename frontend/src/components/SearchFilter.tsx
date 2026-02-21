"use client";

import React from "react";
import { X, Search } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

interface SearchFilterProps {
    searchKeyword: string;
    onSearchChange: (value: string) => void;
    onClearSearch: () => void;
    minScore: number;
    onMinScoreChange: (score: number) => void;
    onApply: () => void;
}

export default function SearchFilter({
    searchKeyword,
    onSearchChange,
    onClearSearch,
    minScore,
    onMinScoreChange,
    onApply,
}: SearchFilterProps) {
    return (
        <Card className="bg-white p-5 rounded-3xl border border-slate-200 shadow-sm flex flex-col gap-5 mx-4">
            {/* Search Input Group */}
            <div className="space-y-2">
                <label className="text-xs font-extrabold text-slate-700 tracking-tight">검색 키워드</label>
                <div className="relative group">
                    <Input
                        type="text"
                        placeholder="지역, 메뉴, 매장명..."
                        className="bg-slate-50 border-slate-100 rounded-xl h-12 text-sm focus-visible:ring-orange-500/10 focus-visible:border-orange-500 text-slate-900 placeholder:text-slate-300 transition-all pr-10 pl-4"
                        value={searchKeyword}
                        onChange={(e) => onSearchChange(e.target.value)}
                        onKeyDown={(e) => {
                            if (e.key === "Enter") onApply();
                        }}
                    />
                    {searchKeyword ? (
                        <button
                            onClick={onClearSearch}
                            className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500 transition-colors p-1"
                        >
                            <X size={14} />
                        </button>
                    ) : (
                        <Search size={14} className="absolute right-4 top-1/2 -translate-y-1/2 text-slate-300" />
                    )}
                </div>
            </div>

            {/* Score Filter Group */}
            <div className="space-y-3">
                <div className="flex justify-between items-center">
                    <label className="text-xs font-extrabold text-slate-700 tracking-tight">최소 AI 점수</label>
                    <span className="text-xs font-extrabold text-orange-700 bg-orange-100 px-2.5 py-1 rounded-full border border-orange-200">{minScore}점 이상</span>
                </div>
                <div className="px-1">
                    <input
                        type="range"
                        min="0"
                        max="90"
                        step="10"
                        value={minScore}
                        onChange={(e) => onMinScoreChange(parseInt(e.target.value))}
                        className="w-full h-1.5 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-orange-500"
                    />
                    <div className="flex justify-between mt-2 px-0.5">
                        {[0, 30, 60, 90].map((tick) => (
                            <span key={tick} className="text-[9px] font-black text-slate-300">{tick}</span>
                        ))}
                    </div>
                </div>
            </div>

            <Button
                type="button"
                onClick={onApply}
                className="h-11 rounded-xl bg-slate-900 hover:bg-slate-800 text-white text-sm font-black"
            >
                조건 적용
            </Button>
        </Card>
    );
}
