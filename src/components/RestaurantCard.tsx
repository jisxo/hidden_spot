import { useState } from "react";
import { ChevronDown, ChevronUp, MapPin, Navigation, Star, X, Utensils, Sparkles, Lightbulb, Copy } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from "@/components/ui/accordion";
import { Card, CardContent } from "@/components/ui/card";

interface RestaurantCardProps {
    restaurant: any;
    onClose: () => void;
}

export default function RestaurantCard({ restaurant, onClose }: RestaurantCardProps) {
    if (!restaurant) return null;

    return (
        <Card className="bg-white/95 backdrop-blur-xl border-none md:border-slate-200 md:ring-1 md:ring-black/5 rounded-t-[32px] md:rounded-3xl shadow-[0_20px_50px_rgba(0,0,0,0.12)] p-0 w-full max-w-md animate-in fade-in slide-in-from-bottom-4 duration-500 overflow-hidden flex flex-col h-full md:h-auto select-none">
            {/* Mobile Drag Handle */}
            <div className="md:hidden w-full flex justify-center pt-2.5 absolute top-0 left-0 z-30 pointer-events-none">
                <div className="w-10 h-1.5 bg-white/20 rounded-full" />
            </div>

            {/* Header Area */}
            <div className="h-20 md:h-24 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 relative flex items-center px-6 shrink-0 pt-4 md:pt-0">
                <button
                    onClick={onClose}
                    className="hidden md:flex absolute top-4 right-4 bg-white/10 hover:bg-white/20 text-white rounded-full p-1.5 transition-all hover:rotate-90 z-20"
                >
                    <X size={18} />
                </button>

                <div className="flex flex-col">
                    <h3 className="text-[9px] font-black text-orange-400 uppercase tracking-[0.2em] mb-0.5 opacity-80">AI Analysis Report</h3>
                    <h2 className="text-xl md:text-2xl font-black text-white leading-tight truncate max-w-[200px] md:max-w-none">{restaurant.name}</h2>
                </div>

                {/* Score Badge */}
                <div className="absolute -bottom-4 md:-bottom-6 right-6 md:right-8 bg-white p-1 rounded-2xl shadow-xl z-20 scale-90 md:scale-100 origin-right">
                    <div className={`w-16 h-16 md:w-20 md:h-20 rounded-xl flex flex-col items-center justify-center font-black text-xl md:text-2xl border-4 border-white ${restaurant.ai_score >= 90 ? 'bg-emerald-600 text-white' :
                        restaurant.ai_score >= 80 ? 'bg-orange-500 text-white' :
                            'bg-slate-700 text-white'
                        }`}>
                        {restaurant.ai_score}
                        <span className="text-[9px] md:text-[10px] font-bold opacity-80 tracking-tighter uppercase mt-[-2px]">점수</span>
                    </div>
                </div>
            </div>

            <CardContent className="flex-1 overflow-y-auto custom-scrollbar pt-2 px-6 pb-8">
                {/* Title & Address Section */}
                <div className="mb-5 relative flex flex-col gap-3">
                    <div className="flex items-center gap-1.5 text-slate-500 text-[11px] font-bold tracking-tight">
                        <MapPin size={12} className="shrink-0 text-slate-300" />
                        <span className="truncate">{restaurant.address}</span>
                        <button
                            onClick={() => {
                                navigator.clipboard.writeText(restaurant.address);
                                const btn = document.getElementById('copy-addr-btn');
                                if (btn) {
                                    btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" class="text-emerald-500"><polyline points="20 6 9 17 4 12"></polyline></svg>';
                                    setTimeout(() => {
                                        btn.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="text-slate-300 hover:text-slate-500"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>';
                                    }, 1500);
                                }
                            }}
                            id="copy-addr-btn"
                            className="ml-1 p-1 hover:bg-slate-100 rounded-md transition-colors cursor-pointer"
                            title="주소 복사"
                        >
                            <Copy size={10} className="text-slate-300 hover:text-slate-500" />
                        </button>
                    </div>

                    {/* View on Naver Maps Link */}
                    {restaurant.original_url && (
                        <div className="flex">
                            <a
                                href={restaurant.original_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="inline-flex items-center gap-2 px-3.5 py-1.5 bg-slate-900 text-white hover:bg-slate-800 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all shadow-lg shadow-black/10"
                            >
                                네이버 지도에서 보기
                                <Navigation size={10} className="text-orange-400" />
                            </a>
                        </div>
                    )}
                </div>

                {/* Transport Info */}
                {restaurant.transport_info && (
                    <div className="mb-6 bg-slate-50 border border-slate-100 rounded-2xl p-3.5">
                        <div className="flex items-center gap-1.5 mb-1.5">
                            <Navigation size={12} className="text-emerald-500" />
                            <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-widest">접근성 가이드</h3>
                        </div>
                        <p className="text-slate-700 text-[13px] font-bold leading-snug">
                            {restaurant.transport_info}
                        </p>
                    </div>
                )}

                {/* Tags (Menus) */}
                <div className="mb-6">
                    <div className="flex items-center gap-2 mb-3">
                        <Utensils size={14} className="text-slate-300" />
                        <h3 className="text-[10px] font-black text-slate-400 uppercase tracking-widest">추천 메뉴</h3>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                        {restaurant.must_eat_menus?.map((menu: string) => (
                            <Badge key={menu} variant="secondary" className="bg-white border-slate-100 text-slate-700 px-3 py-1.5 rounded-xl text-[11px] font-bold shadow-sm">
                                {menu}
                            </Badge>
                        ))}
                    </div>
                </div>

                {/* AI Insights Section */}
                <div className="space-y-4">
                    <div className="flex items-center gap-2 py-1">
                        <Sparkles size={16} className="text-orange-500 fill-orange-500" />
                        <h3 className="text-[11px] font-black text-slate-800 uppercase tracking-widest">AI 미식 가이드</h3>
                    </div>

                    <div className="grid gap-2.5">
                        <div className="bg-slate-50/50 p-4 rounded-2xl border border-slate-100 relative overflow-hidden">
                            <div className="absolute top-0 left-0 w-1 h-full bg-emerald-500" />
                            <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">맛과 특징</span>
                            <p className="text-slate-700 text-[13px] leading-relaxed font-medium">
                                {restaurant.summary_json?.taste}
                            </p>
                        </div>

                        <div className="bg-slate-50/50 p-4 rounded-2xl border border-slate-100 relative overflow-hidden">
                            <div className="absolute top-0 left-0 w-1 h-full bg-blue-500" />
                            <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">공간 & 분위기</span>
                            <p className="text-slate-700 text-[13px] leading-relaxed font-medium">
                                {restaurant.summary_json?.vibe}
                            </p>
                        </div>

                        <div className="bg-slate-50/50 p-4 rounded-2xl border border-slate-100 relative overflow-hidden">
                            <div className="absolute top-0 left-0 w-1 h-full bg-orange-600" />
                            <span className="text-[9px] font-black text-slate-400 uppercase tracking-widest block mb-1">전문가 팁</span>
                            <p className="text-slate-700 text-[13px] leading-relaxed font-medium">
                                {restaurant.summary_json?.tip}
                            </p>
                        </div>
                    </div>
                </div>
            </CardContent>
        </Card>
    );
}

