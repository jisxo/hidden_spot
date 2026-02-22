"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import dynamic from "next/dynamic";
import { RefreshCw, Plus, List, Search, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/components/ui/dialog";
import AddUrlForm from "@/components/AddUrlForm";
import RestaurantCard from "@/components/RestaurantCard";
import CategoryCarousel from "@/components/CategoryCarousel";
import SearchFilter from "@/components/SearchFilter";
import RestaurantList from "@/components/RestaurantList";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

const NaverMap = dynamic(() => import("@/components/Map"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full bg-slate-100 flex items-center justify-center">
      <div className="text-xs font-bold text-slate-500">지도 로딩 중...</div>
    </div>
  ),
});

// Utility: Accurate Distance Calculation (Haversine)
function getDistance(lat1: number, lon1: number, lat2: number, lon2: number) {
  const R = 6371; // km
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a = Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) * Math.sin(dLon / 2);
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
}

type JobCreateResponse = {
  job_id: string;
  run_id: string;
  store_id: string;
  status: "queued" | "completed" | string;
};

type JobSnapshot = {
  run_id?: string;
  store_id?: string;
  status?: string;
  state?: "queued" | "started" | "completed" | "failed" | string;
  error_reason?: string | null;
  error_type?: string | null;
  error_stage?: string | null;
  evidence_paths?: string[];
};

type AnalysisFeedback = {
  type: "success" | "error";
  message: string;
  details?: string[];
};

type MapBounds = {
  north: number;
  south: number;
  east: number;
  west: number;
};

const delay = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));
const DEFAULT_MAP_CENTER = { lat: 37.547241, lng: 127.047325 }; // 뚝섬역

function resolveApiBaseUrl(): string {
  const fallback = "http://localhost:8000";
  const raw = (process.env.NEXT_PUBLIC_API_URL || fallback).trim();
  const normalized = raw.replace(/\/+$/, "");

  if (/^https?:\/\//i.test(normalized)) return normalized;
  if (normalized.startsWith("localhost") || normalized.startsWith("127.0.0.1")) {
    return `http://${normalized}`;
  }
  return `https://${normalized}`;
}

function toErrorTypeLabel(errorType?: string | null): string {
  switch (errorType) {
    case "blocked_suspected":
      return "차단 의심";
    case "parse_failed":
      return "파싱 실패";
    case "crawl_timeout":
      return "크롤링 시간 초과";
    case "llm_failed":
      return "AI 분석 실패";
    case "embed_failed":
      return "임베딩 실패";
    default:
      return "처리 실패";
  }
}

function HomeContent() {
  const [restaurants, setRestaurants] = useState<any[]>([]);
  const API_BASE_URL = resolveApiBaseUrl();

  const [selectedRestaurant, setSelectedRestaurant] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [inputSearchKeyword, setInputSearchKeyword] = useState("");
  const [appliedSearchKeyword, setAppliedSearchKeyword] = useState("");
  const [inputMinScore, setInputMinScore] = useState(0);
  const [appliedMinScore, setAppliedMinScore] = useState(0);
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [isListVisible, setIsListVisible] = useState(false);
  const [mapCenter, setMapCenter] = useState<{ lat: number; lng: number }>(DEFAULT_MAP_CENTER);
  const [mapBounds, setMapBounds] = useState<MapBounds | null>(null);
  const [appliedMapBounds, setAppliedMapBounds] = useState<MapBounds | null>(null);
  const [listSortCenter, setListSortCenter] = useState<{ lat: number; lng: number } | null>(null);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [visibleCount, setVisibleCount] = useState(15);
  const [analysisFeedback, setAnalysisFeedback] = useState<AnalysisFeedback | null>(null);
  const [isFeedbackFading, setIsFeedbackFading] = useState(false);

  const SMART_CATEGORIES = useMemo(() => [
    { id: "all", label: "전체", icon: "🍽️", keywords: [] },
    { id: "soup", label: "탕/찌개", icon: "🥘", keywords: ["탕", "국", "국물", "찌개", "전골", "수프", "해장국", "곰탕", "설렁탕"] },
    { id: "noodle", label: "면", icon: "🍜", keywords: ["면", "국수", "라면", "파스타", "우동", "소바", "짬뽕", "짜장"] },
    { id: "meat", label: "고기", icon: "🥩", keywords: ["고기", "구이", "삼겹살", "갈비", "스테이크", "돈카츠", "돈까스", "치킨", "닭"] },
    { id: "seafood", label: "회", icon: "🍣", keywords: ["회", "일식", "해산물", "사시미", "초밥", "스시", "생선", "조개"] },
  ], []);

  const fetchRestaurants = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (appliedMinScore > 0) params.append("min_score", String(appliedMinScore));
      const res = await fetch(`${API_BASE_URL}/api/v1/restaurants?${params.toString()}`);
      if (!res.ok) throw new Error("Failed to fetch restaurants");
      const data = await res.json();
      const list = Array.isArray(data) ? data : [];
      setRestaurants(list);
      return list;
    } catch (err) {
      console.error(err);
      setRestaurants([]);
      return [];
    }
  }, [API_BASE_URL, appliedMinScore]);

  useEffect(() => {
    fetchRestaurants();
  }, [fetchRestaurants]);

  const handleCenterChange = useCallback((lat: number, lng: number) => {
    setMapCenter((prev) => {
      if (Math.abs(prev.lat - lat) < 0.000001 && Math.abs(prev.lng - lng) < 0.000001) {
        return prev;
      }
      return { lat, lng };
    });
  }, []);

  const handleBoundsChange = useCallback((bounds: MapBounds) => {
    setMapBounds(bounds);
  }, []);

  // Filter Logic
  const filteredRestaurants = useMemo(() => {
    return restaurants.filter((res) => {
      const searchTerms = [appliedSearchKeyword.toLowerCase()];
      const soupKeywords = ['국', '탕', '찌개', '찌게', '전골', '국물'];
      if (soupKeywords.some(k => appliedSearchKeyword.trim() === k)) {
        searchTerms.push('뚝배기', '수프');
      }

      const name = String(res?.name ?? "").toLowerCase();
      const address = String(res?.address ?? "").toLowerCase();
      const menus = Array.isArray(res?.must_eat_menus) ? res.must_eat_menus : [];
      const tags = Array.isArray(res?.search_tags) ? res.search_tags : [];

      const matchesKeyword = appliedSearchKeyword === "" || searchTerms.some(term =>
        name.includes(term) ||
        address.includes(term) ||
        menus.some((m: string) => String(m).toLowerCase().includes(term)) ||
        tags.some((t: string) => String(t).toLowerCase().includes(term))
      );

      const matchesScore = Number(res?.ai_score ?? 0) >= appliedMinScore;

      let matchesCategory = true;
      if (selectedCategory !== "all") {
        const category = SMART_CATEGORIES.find(c => c.id === selectedCategory);
        if (category) {
          matchesCategory = tags.some((tag: string) =>
            category.keywords.some(kw => String(tag).includes(kw))
          ) || menus.some((menu: string) =>
            category.keywords.some(kw => String(menu).includes(kw))
          );
        }
      }

      const lat = Number(res?.latitude);
      const lng = Number(res?.longitude);
      const matchesMapArea =
        !appliedMapBounds ||
        (Number.isFinite(lat) &&
          Number.isFinite(lng) &&
          lat <= appliedMapBounds.north &&
          lat >= appliedMapBounds.south &&
          lng <= appliedMapBounds.east &&
          lng >= appliedMapBounds.west);

      return matchesKeyword && matchesScore && matchesCategory && matchesMapArea;
    });
  }, [restaurants, appliedSearchKeyword, appliedMinScore, selectedCategory, SMART_CATEGORIES, appliedMapBounds]);

  // Sort Logic (Decoupled from real-time map move)
  const sortedRestaurants = useMemo(() => {
    if (!listSortCenter) return [...filteredRestaurants];
    return [...filteredRestaurants].sort((a, b) => {
      const aLat = Number(a?.latitude ?? 37.5665);
      const aLng = Number(a?.longitude ?? 126.978);
      const bLat = Number(b?.latitude ?? 37.5665);
      const bLng = Number(b?.longitude ?? 126.978);
      const distA = getDistance(listSortCenter.lat, listSortCenter.lng, aLat, aLng);
      const distB = getDistance(listSortCenter.lat, listSortCenter.lng, bLat, bLng);
      return distA - distB;
    });
  }, [filteredRestaurants, listSortCenter]);

  // Paginated View
  const paginatedRestaurants = useMemo(() => {
    return sortedRestaurants.slice(0, visibleCount);
  }, [sortedRestaurants, visibleCount]);

  // Reset pagination when filters change
  useEffect(() => {
    setVisibleCount(15);
  }, [appliedSearchKeyword, appliedMinScore, selectedCategory]);

  const handleShowMore = () => {
    setVisibleCount(prev => prev + 15);
  };


  // Initial Sorting Center
  useEffect(() => {
    if (mapCenter && !listSortCenter) {
      setListSortCenter(mapCenter);
    }
  }, [mapCenter, listSortCenter]);

  useEffect(() => {
    if (!analysisFeedback) {
      setIsFeedbackFading(false);
      return;
    }
    if (analysisFeedback.type !== "success" || analysisFeedback.message !== "분석이 완료되었습니다.") {
      setIsFeedbackFading(false);
      return;
    }

    const fadeTimer = window.setTimeout(() => setIsFeedbackFading(true), 2000);
    const hideTimer = window.setTimeout(() => {
      setAnalysisFeedback(null);
      setIsFeedbackFading(false);
    }, 2400);

    return () => {
      window.clearTimeout(fadeTimer);
      window.clearTimeout(hideTimer);
    };
  }, [analysisFeedback]);

  const handleRefreshList = () => {
    setListSortCenter(mapCenter);
    setAppliedMapBounds(mapBounds);
    setIsListVisible(true);
  };

  const handleSearchChange = (val: string) => {
    setInputSearchKeyword(val);
    if (val.trim()) {
      setIsListVisible(true);
    }
  };

  const handleMinScoreChange = (score: number) => {
    setInputMinScore(score);
  };

  const handleApplyFilters = () => {
    setAppliedSearchKeyword(inputSearchKeyword.trim());
    setAppliedMinScore(inputMinScore);
    setIsListVisible(true);
  };

  const clearSearch = () => {
    setInputSearchKeyword("");
    setAppliedSearchKeyword("");
    setIsListVisible(false);
  };

  const isInvalidUrl = (value: string) => {
    try {
      const parsed = new URL(value.trim());
      return parsed.protocol !== "http:" && parsed.protocol !== "https:";
    } catch {
      return true;
    }
  };

  const waitForJobCompletion = useCallback(
    async (jobId: string): Promise<JobSnapshot | null> => {
      let lastSnapshot: JobSnapshot | null = null;
      for (let i = 0; i < 60; i += 1) {
        const res = await fetch(`${API_BASE_URL}/jobs/${jobId}`);
        if (!res.ok) break;
        const snapshot = (await res.json()) as JobSnapshot;
        lastSnapshot = snapshot;
        const state = snapshot.state || snapshot.status;
        if (state === "completed" || state === "failed") return snapshot;
        await delay(1500);
      }
      return lastSnapshot;
    },
    [API_BASE_URL]
  );

  const handleAnalyze = async (url: string) => {
    setIsLoading(true);
    setAnalysisFeedback(null);
    try {
      if (isInvalidUrl(url)) {
        throw new Error("유효한 URL을 입력해 주세요.");
      }

      const res = await fetch(`${API_BASE_URL}/jobs`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || errorData.message || "작업 생성에 실패했습니다.");
      }
      const job = (await res.json()) as JobCreateResponse;
      setAnalysisFeedback({
        type: "success",
        message: "분석 요청을 접수했습니다. 결과를 가져오는 중입니다.",
      });

      const snapshot = await waitForJobCompletion(job.job_id);
      const state = snapshot?.state || snapshot?.status || job.status;
      if (state === "failed") {
        const typeLabel = toErrorTypeLabel(snapshot?.error_type);
        const reason = snapshot?.error_reason || "분석 처리 중 문제가 발생했습니다.";
        const evidence = snapshot?.evidence_paths?.[0];
        setAnalysisFeedback({
          type: "error",
          message: `${typeLabel} (${snapshot?.error_type || "unknown_failed"})`,
          details: [
            reason,
            evidence ? `증거 경로: ${evidence}` : "증거 경로: 없음",
          ],
        });
        return;
      }

      if (state !== "completed") {
        setAnalysisFeedback({
          type: "success",
          message: "분석 요청이 접수되었습니다. 처리 완료 후 리스트에 반영됩니다.",
          details: [`run_id: ${job.run_id}`],
        });
        return;
      }

      const refreshed = await fetchRestaurants();
      const target = refreshed.find((r) => r.id === job.store_id);
      if (target) {
        setSelectedRestaurant(target);
      }
      setIsListVisible(false);
      setAnalysisFeedback({
        type: "success",
        message: "분석이 완료되었습니다.",
      });
    } catch (err: any) {
      console.error(err);
      setAnalysisFeedback({
        type: "error",
        message: "처리 실패",
        details: [err.message || "분석 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."],
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <main className="relative w-full h-screen overflow-hidden bg-white font-sans text-slate-900 flex flex-col md:flex-row" suppressHydrationWarning>
      {/* Sidebar Area */}
      <aside className={`order-2 md:order-1 w-full md:w-[400px] bg-slate-50 border-t md:border-t-0 md:border-r border-slate-200 z-20 flex flex-col relative shadow-[0_-10px_30px_rgba(0,0,0,0.05)] md:shadow-none transition-all duration-300 ${isListVisible ? 'h-[52vh] md:h-full' : 'h-0 md:h-full overflow-hidden md:overflow-visible pointer-events-none md:pointer-events-auto'}`}>
        <header className="p-6 bg-white border-b border-slate-100 flex-none z-10 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-black tracking-tight text-slate-900 mb-0.5 font-display uppercase italic text-shadow-sm">HIDDEN SPOT</h1>
            <p className="text-slate-400 text-[10px] font-bold uppercase tracking-widest leading-none">프리미엄 맛집 큐레이션</p>
          </div>
          <Badge className="bg-orange-500 hover:bg-orange-600 text-white text-[10px] font-black px-2 py-0.5 rounded-md border-none">BETA</Badge>
        </header>

        <div className="p-4 flex-none hidden md:block">
          <AddUrlForm onAnalyze={handleAnalyze} isLoading={isLoading} />
        </div>

        <ScrollArea className="flex-1 min-h-0">
          <div className="space-y-6 py-5">
            <div className="hidden md:block">
              <SearchFilter
                searchKeyword={inputSearchKeyword}
                onSearchChange={handleSearchChange}
                onClearSearch={clearSearch}
                minScore={inputMinScore}
                onMinScoreChange={handleMinScoreChange}
                onApply={handleApplyFilters}
              />
            </div>

            <CategoryCarousel
              categories={SMART_CATEGORIES}
              selectedCategory={selectedCategory}
              onSelectCategory={setSelectedCategory}
            />

            <div className="md:hidden flex items-center justify-between px-6 mb-2">
              <h2 className="text-[10px] font-black text-slate-400 uppercase tracking-widest">
                {selectedCategory !== 'all' ? SMART_CATEGORIES.find(c => c.id === selectedCategory)?.label : '검색 결과'} ({sortedRestaurants.length})
              </h2>
            </div>

            <RestaurantList
              restaurants={paginatedRestaurants}
              selectedId={selectedRestaurant?.id}
              onSelect={(res) => { setSelectedRestaurant(res); setIsListVisible(false); }}
              showActions={false}
              isLoading={isLoading}
            />

            {sortedRestaurants.length > visibleCount && (
              <div className="px-4 pb-10">
                <Button
                  onClick={handleShowMore}
                  variant="outline"
                  className="w-full h-12 rounded-2xl border-slate-200 text-slate-500 font-black text-xs hover:bg-slate-50 hover:text-slate-900 transition-all flex items-center justify-center gap-2"
                >
                  <Plus size={14} />
                  결과 더보기 ({sortedRestaurants.length - visibleCount}개 남음)
                </Button>
              </div>
            )}
          </div>
        </ScrollArea>
      </aside>

      {/* Map Area */}
      <section className={`order-1 md:order-2 flex-1 relative bg-slate-100 ${isListVisible ? "h-[48vh]" : "h-[100vh]"} md:h-full`}>
        {/* Mobile Map Search Header */}
        <div className="md:hidden absolute top-4 left-4 right-20 z-30 pointer-events-none">
          <div className="pointer-events-auto bg-white/90 backdrop-blur-xl border border-slate-200 rounded-2xl shadow-xl flex items-center px-4 h-12 ring-1 ring-black/5">
            <Search className="text-slate-400 mr-3" size={18} />
            <input
              type="text"
              placeholder="맛집 검색..."
              className="flex-1 bg-transparent border-none text-sm focus:outline-none text-slate-900 placeholder:text-slate-400 font-bold"
              value={inputSearchKeyword}
              onChange={(e) => handleSearchChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleApplyFilters();
              }}
            />
            {inputSearchKeyword && (
              <button
                onClick={clearSearch}
                className="ml-2 p-1 text-slate-300 hover:text-slate-500"
              >
                <X size={16} />
              </button>
            )}
            <button
              onClick={handleApplyFilters}
              className="ml-2 text-[10px] font-black text-slate-700 rounded-md border border-slate-200 px-2 py-1"
            >
              조건 적용
            </button>
          </div>
        </div>
        <div className="md:hidden absolute top-4 right-4 z-30">
          <div className="rounded-xl bg-white/90 border border-slate-200 p-1 shadow">
            <button
              type="button"
              onClick={() => setIsListVisible(false)}
              aria-pressed={!isListVisible}
              className={`px-2 py-1 text-[10px] font-black rounded-md transition-colors ${!isListVisible ? "bg-slate-900 text-white" : "text-slate-500"}`}
            >
              MAP
            </button>
            <button
              type="button"
              onClick={() => setIsListVisible(true)}
              aria-pressed={isListVisible}
              className={`ml-1 px-2 py-1 text-[10px] font-black rounded-md transition-colors ${isListVisible ? "bg-slate-900 text-white" : "text-slate-500"}`}
            >
              LIST
            </button>
          </div>
        </div>

        <NaverMap
          restaurants={filteredRestaurants}
          selectedId={selectedRestaurant?.id}
          onMarkerClick={(res) => { setSelectedRestaurant(res); setIsListVisible(false); }}
          onMapClick={() => { setSelectedRestaurant(null); setIsListVisible(false); }}
          onCenterChange={handleCenterChange}
          onBoundsChange={handleBoundsChange}
          initialCenter={DEFAULT_MAP_CENTER}
        />

        {/* Floating "Search in this area" Button */}
        {mapCenter && listSortCenter && (
          <div className="absolute bottom-24 md:bottom-12 left-1/2 -translate-x-1/2 z-30 transition-all">
            <Button
              onClick={handleRefreshList}
              className={`bg-white/95 backdrop-blur-md text-slate-900 border border-slate-200 rounded-full px-6 h-12 font-black text-xs shadow-2xl hover:bg-slate-900 hover:text-white transition-all gap-2 transform active:scale-95 ${Math.abs(mapCenter.lat - listSortCenter.lat) < 0.0001 && Math.abs(mapCenter.lng - listSortCenter.lng) < 0.0001
                ? 'opacity-0 scale-90 pointer-events-none translate-y-4'
                : 'opacity-100 scale-100 translate-y-0'
                }`}
            >
              <RefreshCw size={14} className={isLoading ? "animate-spin" : ""} />
              현지도에서 재검색
            </Button>
          </div>
        )}

        {/* FABs for Mobile */}
        <div className="md:hidden absolute bottom-6 right-6 z-50 flex flex-col gap-3">
          <button
            aria-label={isListVisible ? "Hide list view" : "Show list view"}
            onClick={() => setIsListVisible(!isListVisible)}
            className={`w-12 h-12 rounded-full shadow-xl flex items-center justify-center transition-all ${isListVisible ? 'bg-orange-500 text-white' : 'bg-white text-slate-600 border'}`}
          >
            <List size={22} />
          </button>
          <Dialog open={isRegisterOpen} onOpenChange={setIsRegisterOpen}>
            <DialogTrigger asChild>
              <button className="w-14 h-14 bg-slate-900 rounded-full shadow-2xl flex items-center justify-center text-white"><Plus size={28} /></button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px] rounded-3xl p-0 bg-transparent border-none shadow-none">
              <DialogHeader className="sr-only">
                <DialogTitle>맛집 등록</DialogTitle>
                <DialogDescription>새로운 맛집의 네이버 지도 URL을 입력하여 분석합니다.</DialogDescription>
              </DialogHeader>
              <AddUrlForm onAnalyze={(url) => { handleAnalyze(url); setIsRegisterOpen(false); }} isLoading={isLoading} />
            </DialogContent>
          </Dialog>
        </div>

        {/* Detail Card Overlay */}
        {selectedRestaurant && (
          <div className="fixed inset-0 md:absolute md:inset-auto md:bottom-8 md:right-8 z-[60] flex items-end md:items-initial justify-center md:justify-end transition-all">
            {/* Mobile Backdrop: Closes on click */}
            <div
              className="md:hidden absolute inset-0 bg-slate-900/40 backdrop-blur-sm"
              onClick={() => setSelectedRestaurant(null)}
            />

            {/* Card Container: Fixed height on mobile for internal scrolling */}
            <div className="relative w-full md:w-[400px] h-[85vh] md:h-[85vh] bg-white md:bg-transparent rounded-t-[32px] md:rounded-3xl shadow-2xl overflow-hidden animate-in slide-in-from-bottom-full duration-500 cubic-bezier(0.16, 1, 0.3, 1)">
              <div className="w-full h-full">
                <RestaurantCard restaurant={selectedRestaurant} onClose={() => setSelectedRestaurant(null)} />
              </div>
            </div>
          </div>
        )}
      </section>

      {analysisFeedback && (
        <div className={`fixed left-3 top-3 z-[130] rounded-xl border bg-white/95 px-3 py-2 shadow-lg transition-opacity duration-400 ${isFeedbackFading ? "opacity-0" : "opacity-100"}`}>
          <p className={`text-xs font-black ${analysisFeedback.type === "error" ? "text-rose-600" : "text-emerald-600"}`}>
            {analysisFeedback.type === "error" ? "오류 안내" : "분석 상태"}
          </p>
          <p className="text-[11px] font-semibold text-slate-700">{analysisFeedback.message}</p>
          {analysisFeedback.details?.map((line, idx) => (
            <p key={`${line}-${idx}`} className="text-[11px] text-slate-600 break-all">
              {line}
            </p>
          ))}
          {analysisFeedback.type === "error" && (
            <button
              onClick={() => setAnalysisFeedback(null)}
              className="mt-2 text-[11px] font-bold text-slate-500 underline"
            >
              닫기
            </button>
          )}
        </div>
      )}

    </main>
  );
}

export default HomeContent;
