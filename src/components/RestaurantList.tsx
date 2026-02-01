"use client";

import React from "react";
import { MapPin, Navigation, RefreshCw, Trash2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

interface RestaurantListProps {
    restaurants: any[];
    selectedId: string | null;
    onSelect: (res: any) => void;
    onRefresh: (id: string) => void;
    onDelete: (id: string) => void;
    refreshingId: string | null;
    isLoading: boolean;
}

export default function RestaurantList({
    restaurants,
    selectedId,
    onSelect,
    onRefresh,
    onDelete,
    refreshingId,
    isLoading,
}: RestaurantListProps) {
    if (isLoading && restaurants.length === 0) {
        return (
            <div className="space-y-4 px-4 py-2">
                {[1, 2, 3].map((i) => (
                    <Skeleton key={i} className="h-32 w-full rounded-[24px] bg-slate-200/50" />
                ))}
            </div>
        );
    }

    if (restaurants.length === 0) {
        return (
            <div className="flex flex-col items-center justify-center py-20 px-10 text-center space-y-4">
                <div className="w-16 h-16 bg-slate-100 rounded-full flex items-center justify-center text-slate-300">
                    <MapPin size={32} />
                </div>
                <div className="space-y-1">
                    <h3 className="text-slate-900 font-black text-sm uppercase tracking-tight">맛집이 없습니다</h3>
                    <p className="text-slate-400 text-[11px] font-bold leading-relaxed">조건에 맞는 장소를 찾지 못했습니다.<br />필터를 조정하거나 새로운 URL을 등록하세요.</p>
                </div>
            </div>
        );
    }

    return (
        <div className="flex flex-col gap-4 px-4 pb-20">
            {restaurants.map((res) => (
                <div
                    key={res.id}
                    onClick={() => onSelect(res)}
                    className={`group relative bg-white p-5 rounded-[28px] border transition-all cursor-pointer hover:shadow-[0_20px_40px_rgba(0,0,0,0.06)] hover:-translate-y-1.5 ${selectedId === res.id
                        ? "border-slate-900 ring-4 ring-slate-900/5 z-10"
                        : "border-slate-100 hover:border-slate-200"
                        }`}
                >
                    <div className="flex justify-between items-start gap-4">
                        {/* Left Side: Info */}
                        <div className="flex-1 min-w-0">
                            {/* Title row */}
                            <div className="flex items-center gap-2 mb-2">
                                {res.ai_score >= 90 && (
                                    <span className="text-[9px] font-black bg-emerald-500 text-white px-1.5 py-0.5 rounded-md uppercase tracking-tighter shrink-0">Gold Tier</span>
                                )}
                                <h3 className="font-black text-slate-900 text-base leading-tight group-hover:text-slate-900 transition-colors uppercase tracking-tight truncate">
                                    {res.name}
                                </h3>
                            </div>

                            {/* Info Section: STRICT VERTICAL STACK */}
                            <div className="flex flex-col gap-2 mt-3 w-full">
                                {/* Row 1: Address */}
                                <div className="flex items-start gap-2 text-[11px] font-black text-slate-400 w-full">
                                    <MapPin size={12} className="shrink-0 text-slate-300 mt-0.5" />
                                    <div className="flex-1">{res.address.split(" ").slice(0, 3).join(" ")}</div>
                                </div>
                                {/* Row 2: Transport */}
                                <div className="flex items-start gap-2 text-[12px] font-black text-slate-600 w-full min-w-0">
                                    <Navigation size={12} className="shrink-0 text-slate-400 mt-0.5" />
                                    <div className="flex-1">{res.transport_info?.split(",")[0] || "정보 없음"}</div>
                                </div>
                            </div>

                            {/* Menu Tags */}
                            {res.must_eat_menus && res.must_eat_menus.length > 0 && (
                                <div className="flex flex-wrap gap-1.5 mt-4">
                                    {res.must_eat_menus.slice(0, 3).map((menu: string) => {
                                        const isSignature = menu.includes("⭐");
                                        return (
                                            <span
                                                key={menu}
                                                className={`text-[10px] font-black px-2 py-1 rounded-lg border transition-colors ${isSignature
                                                    ? "bg-slate-900 text-white border-slate-900"
                                                    : "bg-slate-50 text-slate-500 border-slate-100/50 group-hover:bg-white group-hover:border-slate-200"
                                                    }`}
                                            >
                                                {menu.replace("⭐", "").trim()}
                                                {isSignature && <span className="ml-1 text-[8px] opacity-70">TOP</span>}
                                            </span>
                                        );
                                    })}
                                </div>
                            )}
                        </div>

                        {/* Right Side: Score & Actions */}
                        <div className="flex flex-col items-end gap-3 shrink-0">
                            <div className={`w-12 h-12 rounded-2xl text-[14px] font-black flex flex-col items-center justify-center shrink-0 shadow-lg border-2 border-white ${res.ai_score >= 90 ? "bg-emerald-500 text-white shadow-emerald-500/10" :
                                res.ai_score >= 80 ? "bg-slate-900 text-white shadow-slate-900/10" :
                                    "bg-slate-200 text-slate-600 shadow-slate-200/10"
                                }`}>
                                {res.ai_score}
                            </div>

                            <div className="flex items-center gap-1">
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onRefresh(res.id);
                                    }}
                                    disabled={refreshingId === res.id}
                                    className={`p-2.5 text-slate-300 hover:text-slate-900 hover:bg-slate-50 rounded-xl transition-all ${refreshingId === res.id ? "opacity-100" : ""}`}
                                >
                                    <RefreshCw
                                        size={16}
                                        className={refreshingId === res.id ? "animate-spin text-slate-900" : ""}
                                    />
                                </button>
                                <button
                                    onClick={(e) => {
                                        e.stopPropagation();
                                        onDelete(res.id);
                                    }}
                                    className="p-2.5 text-slate-300 hover:text-rose-500 hover:bg-rose-50 rounded-xl transition-all"
                                >
                                    <Trash2 size={16} />
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            ))}
        </div>
    );
}
