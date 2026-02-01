"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { Trash2, RefreshCw, Plus, List, Search, X } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogTrigger,
} from "@/components/ui/dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import Map from "@/components/Map";
import AddUrlForm from "@/components/AddUrlForm";
import RestaurantCard from "@/components/RestaurantCard";
import CategoryCarousel from "@/components/CategoryCarousel";
import SearchFilter from "@/components/SearchFilter";
import RestaurantList from "@/components/RestaurantList";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Skeleton } from "@/components/ui/skeleton";

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

export default function Home() {
  const [restaurants, setRestaurants] = useState<any[]>([]);
  const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
  const [selectedRestaurant, setSelectedRestaurant] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [isListVisible, setIsListVisible] = useState(false);
  const [mapCenter, setMapCenter] = useState<{ lat: number; lng: number }>({ lat: 37.5665, lng: 126.9780 });
  const [listSortCenter, setListSortCenter] = useState<{ lat: number; lng: number } | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [confirmRefreshId, setConfirmRefreshId] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const [visibleCount, setVisibleCount] = useState(15);

  const SMART_CATEGORIES = useMemo(() => [
    { id: 'all', label: '전체', icon: '🍽️', keywords: [] },
    { id: 'soup', label: '탕/찌개', icon: '🥘', keywords: ['탕', '국', '국물', '찌개', '전골', '수프', '해장국', '곰탕', '설렁탕'] },
    { id: 'noodle', label: '면', icon: '🍜', keywords: ['면', '국수', '라면', '파스타', '우동', '소바', '짬뽕', '짜장'] },
    { id: 'meat', label: '고기', icon: '🥩', keywords: ['고기', '구이', '삼겹살', '갈비', '스테이크', '돈카츠', '돈까스', '치킨', '닭'] },
    { id: 'seafood', label: '회', icon: '🍣', keywords: ['회', '일식', '해산물', '사시미', '초밥', '스시', '생선', '조개'] },
  ], []);

  // Filter Logic
  const filteredRestaurants = useMemo(() => {
    return restaurants.filter((res) => {
      const searchTerms = [searchKeyword.toLowerCase()];
      const soupKeywords = ['국', '탕', '찌개', '찌게', '전골', '국물'];
      if (soupKeywords.some(k => searchKeyword.trim() === k)) {
        searchTerms.push('뚝배기', '수프');
      }

      const matchesKeyword = searchKeyword === "" || searchTerms.some(term =>
        res.name.toLowerCase().includes(term) ||
        res.address.toLowerCase().includes(term) ||
        res.must_eat_menus?.some((m: string) => m.toLowerCase().includes(term)) ||
        res.search_tags?.some((t: string) => t.toLowerCase().includes(term))
      );

      const matchesScore = res.ai_score >= minScore;

      let matchesCategory = true;
      if (selectedCategory !== "all") {
        const category = SMART_CATEGORIES.find(c => c.id === selectedCategory);
        if (category) {
          matchesCategory = res.search_tags?.some((tag: string) =>
            category.keywords.some(kw => tag.includes(kw))
          ) || res.must_eat_menus?.some((menu: string) =>
            category.keywords.some(kw => menu.includes(kw))
          );
        }
      }

      return matchesKeyword && matchesScore && matchesCategory;
    });
  }, [restaurants, searchKeyword, minScore, selectedCategory, SMART_CATEGORIES]);

  // Sort Logic (Decoupled from real-time map move)
  const sortedRestaurants = useMemo(() => {
    if (!listSortCenter) return [...filteredRestaurants];
    return [...filteredRestaurants].sort((a, b) => {
      const distA = getDistance(listSortCenter.lat, listSortCenter.lng, a.latitude, a.longitude);
      const distB = getDistance(listSortCenter.lat, listSortCenter.lng, b.latitude, b.longitude);
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
  }, [searchKeyword, minScore, selectedCategory]);

  const handleShowMore = () => {
    setVisibleCount(prev => prev + 15);
  };

  // Fetch Logic
  const fetchRestaurants = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (minScore > 0) params.append("min_score", minScore.toString());
      const res = await fetch(`${API_BASE_URL}/api/v1/restaurants?${params.toString()}`);
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      setRestaurants(data);
    } catch (err) {
      console.error(err);
    }
  }, [minScore]);

  useEffect(() => {
    fetchRestaurants();
  }, [fetchRestaurants]);

  // Initial Sorting Center
  useEffect(() => {
    if (mapCenter && !listSortCenter) {
      setListSortCenter(mapCenter);
    }
  }, [mapCenter, listSortCenter]);

  const handleRefreshList = () => {
    setListSortCenter(mapCenter);
    setIsListVisible(true);
  };

  const handleSearchChange = (val: string) => {
    setSearchKeyword(val);
    if (val.trim()) {
      setIsListVisible(true);
    }
  };

  const clearSearch = () => {
    setSearchKeyword("");
    setIsListVisible(false);
  };

  const handleAnalyze = async (url: string) => {
    setIsLoading(true);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/restaurants/analyze`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        throw new Error(errorData.detail || "Analysis failed");
      }
      const data = await res.json();
      setSelectedRestaurant(data.restaurant);
      setIsListVisible(false);
      fetchRestaurants();
    } catch (err: any) {
      console.error(err);
      alert(`분석 중 오류 발생: ${err.message}`);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await fetch(`${API_BASE_URL}/api/v1/restaurants/${id}`, { method: "DELETE" });
      if (selectedRestaurant?.id === id) setSelectedRestaurant(null);
      fetchRestaurants();
    } catch (err) {
      console.error(err);
    } finally {
      setConfirmDeleteId(null);
    }
  };

  const handleRefresh = async (id: string) => {
    setRefreshingId(id);
    try {
      const res = await fetch(`${API_BASE_URL}/api/v1/restaurants/${id}/refresh`, { method: "POST" });
      if (!res.ok) throw new Error("Refresh failed");
      const data = await res.json();
      if (selectedRestaurant?.id === id) setSelectedRestaurant(data.restaurant);
      fetchRestaurants();
    } catch (err) {
      console.error(err);
    } finally {
      setRefreshingId(null);
      setConfirmRefreshId(null);
    }
  };

  return (
    <main className="relative w-full h-screen overflow-hidden bg-white font-sans text-slate-900 flex flex-col md:flex-row">
      {/* Sidebar Area */}
      <aside className={`order-2 md:order-1 w-full md:w-[400px] bg-slate-50 border-t md:border-t-0 md:border-r border-slate-200 z-20 flex flex-col relative shadow-[0_-10px_30px_rgba(0,0,0,0.05)] md:shadow-none transition-all duration-300 ${isListVisible ? 'h-[50vh] md:h-full' : 'h-0 md:h-full overflow-hidden md:overflow-visible'}`}>
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
                searchKeyword={searchKeyword}
                onSearchChange={handleSearchChange}
                onClearSearch={clearSearch}
                minScore={minScore}
                onMinScoreChange={setMinScore}
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
              onRefresh={setConfirmRefreshId}
              onDelete={setConfirmDeleteId}
              refreshingId={refreshingId}
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
      <section className="order-1 md:order-2 flex-1 relative bg-slate-100 h-[50vh] md:h-full">
        {/* Mobile Map Search Header */}
        <div className="md:hidden absolute top-4 left-4 right-4 z-30 pointer-events-none">
          <div className="pointer-events-auto bg-white/90 backdrop-blur-xl border border-slate-200 rounded-2xl shadow-xl flex items-center px-4 h-12 ring-1 ring-black/5">
            <Search className="text-slate-400 mr-3" size={18} />
            <input
              type="text"
              placeholder="맛집 검색..."
              className="flex-1 bg-transparent border-none text-sm focus:outline-none text-slate-900 placeholder:text-slate-400 font-bold"
              value={searchKeyword}
              onChange={(e) => handleSearchChange(e.target.value)}
            />
            {searchKeyword && (
              <button
                onClick={clearSearch}
                className="ml-2 p-1 text-slate-300 hover:text-slate-500"
              >
                <X size={16} />
              </button>
            )}
          </div>
        </div>

        <Map
          restaurants={restaurants}
          selectedId={selectedRestaurant?.id}
          onMarkerClick={(res) => { setSelectedRestaurant(res); setIsListVisible(false); }}
          onMapClick={() => { setSelectedRestaurant(null); setIsListVisible(false); }}
          onCenterChange={(lat, lng) => setMapCenter({ lat, lng })}
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
          <button onClick={() => setIsListVisible(!isListVisible)} className={`w-12 h-12 rounded-full shadow-xl flex items-center justify-center transition-all ${isListVisible ? 'bg-orange-500 text-white' : 'bg-white text-slate-600 border'}`}>
            <List size={22} />
          </button>
          <Dialog open={isRegisterOpen} onOpenChange={setIsRegisterOpen}>
            <DialogTrigger asChild>
              <button className="w-14 h-14 bg-slate-900 rounded-full shadow-2xl flex items-center justify-center text-white"><Plus size={28} /></button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px] rounded-3xl p-0 bg-transparent border-none shadow-none">
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

      {/* Modals */}
      <AlertDialog open={!!confirmRefreshId} onOpenChange={() => setConfirmRefreshId(null)}>
        <AlertDialogContent className="rounded-3xl border-none p-6 bg-white shadow-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-xl font-black text-slate-900 uppercase tracking-tight">정보 업데이트</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-500 font-medium">최신 리뷰를 바탕으로 정보를 다시 분석할까요? <br /><span className="text-orange-600 font-bold mt-1 inline-block">(약 10-20초 소요)</span></AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="mt-4 gap-2">
            <AlertDialogCancel className="rounded-2xl border-slate-100 bg-slate-50 font-bold text-slate-600 h-12 px-6">취소</AlertDialogCancel>
            <AlertDialogAction onClick={() => confirmRefreshId && handleRefresh(confirmRefreshId)} className="rounded-2xl bg-slate-900 hover:bg-slate-800 text-white font-bold h-12 px-6">분석 시작</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      <AlertDialog open={!!confirmDeleteId} onOpenChange={() => setConfirmDeleteId(null)}>
        <AlertDialogContent className="rounded-3xl border-none p-6 bg-white shadow-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-xl font-black text-slate-900 uppercase tracking-tight">맛집 삭제</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-500 font-medium">정말 삭제하시겠습니까? <br /><span className="text-red-500 font-bold mt-1 inline-block">데이터는 복구할 수 없습니다.</span></AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="mt-4 gap-2">
            <AlertDialogCancel className="rounded-2xl border-slate-100 bg-slate-50 font-bold text-slate-600 h-12 px-6">취소</AlertDialogCancel>
            <AlertDialogAction onClick={() => confirmDeleteId && handleDelete(confirmDeleteId)} className="rounded-2xl bg-red-500 hover:bg-red-600 text-white font-bold h-12 px-6">삭제하기</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </main>
  );
}
