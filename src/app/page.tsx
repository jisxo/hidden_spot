"use client";

import { useState, useEffect, useCallback, useMemo, useRef } from "react";
import { Trash2, X, RefreshCw, MapPin, Navigation, Plus, Search, List, ChevronLeft, ChevronRight } from "lucide-react";
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
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ScrollArea, ScrollBar } from "@/components/ui/scroll-area";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";

export default function Home() {
  const [restaurants, setRestaurants] = useState<any[]>([]);
  const [selectedRestaurant, setSelectedRestaurant] = useState<any>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [searchKeyword, setSearchKeyword] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [refreshingId, setRefreshingId] = useState<string | null>(null);
  const [isRegisterOpen, setIsRegisterOpen] = useState(false);
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const [isListVisible, setIsListVisible] = useState(false);
  const [mapCenter, setMapCenter] = useState({ lat: 37.5665, lng: 126.9780 });
  const [touchStart, setTouchStart] = useState<number | null>(null);
  const [touchEnd, setTouchEnd] = useState<number | null>(null);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [confirmRefreshId, setConfirmRefreshId] = useState<string | null>(null);
  const [selectedCategory, setSelectedCategory] = useState("all");
  const categoryScrollRef = useRef<HTMLDivElement>(null);

  const scrollCategories = (direction: 'left' | 'right') => {
    if (categoryScrollRef.current) {
      const scrollAmount = 200;
      categoryScrollRef.current.scrollBy({
        left: direction === 'right' ? scrollAmount : -scrollAmount,
        behavior: 'smooth'
      });
    }
  };

  const SMART_CATEGORIES = [
    { id: 'all', label: '전체', icon: '🍽️', keywords: [] },
    { id: 'soup', label: '탕/찌개', icon: '🥘', keywords: ['탕', '국', '국물', '찌개', '전골', '수프', '해장국', '곰탕', '설렁탕'] },
    { id: 'noodle', label: '면', icon: '🍜', keywords: ['면', '국수', '라면', '파스타', '우동', '소바', '짬뽕', '짜장'] },
    { id: 'meat', label: '고기', icon: '🥩', keywords: ['고기', '구이', '삼겹살', '갈비', '스테이크', '돈카츠', '돈까스', '치킨', '닭'] },
    { id: 'seafood', label: '회', icon: '🍣', keywords: ['회', '일식', '해산물', '사시미', '초밥', '스시', '생선', '조개'] },
  ];

  const filteredRestaurants = useMemo(() => {
    return restaurants.filter((res) => {
      // Synonym Expansion for Search
      let searchTerms = [searchKeyword.toLowerCase()];
      const soupKeywords = ['국', '탕', '찌개', '찌게', '전골', '국물'];

      // If the user's input strictly matches one of the soup keywords (or typograph '찌게')
      if (soupKeywords.some(k => searchKeyword.trim() === k)) {
        searchTerms = ['국', '탕', '찌개', '전골', '국물', '뚝배기', '수프'];
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

  // Separate state for sorting center to prevent list jumping on selection
  const [userMapCenter, setUserMapCenter] = useState({ lat: 37.5665, lng: 126.9780 });

  const sortedRestaurants = useMemo(() => {
    return [...filteredRestaurants].sort((a, b) => {
      // Use userMapCenter for sorting, not the visual mapCenter
      const distA = Math.pow(a.latitude - userMapCenter.lat, 2) + Math.pow(a.longitude - userMapCenter.lng, 2);
      const distB = Math.pow(b.latitude - userMapCenter.lat, 2) + Math.pow(b.longitude - userMapCenter.lng, 2);
      return distA - distB;
    });
  }, [filteredRestaurants, userMapCenter]);

  const fetchRestaurants = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      if (minScore > 0) params.append("min_score", minScore.toString());
      // No longer sending searchKeyword to server to allow instant local filtering

      const res = await fetch(`http://localhost:8000/api/v1/restaurants?${params.toString()}`);
      if (!res.ok) throw new Error("Failed to fetch");
      const data = await res.json();
      setRestaurants(data);
    } catch (err) {
      console.error(err);
    }
  }, [minScore]); // Only re-fetch when base score filter changes

  useEffect(() => {
    fetchRestaurants();
  }, [fetchRestaurants]);

  const handleAnalyze = async (url: string) => {
    setIsLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/restaurants/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      });
      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || "Analysis failed");
      }
      const newRestaurant = await res.json();
      setSelectedRestaurant(newRestaurant);
      setIsListVisible(false); // Hide list when a specific restaurant is analyzed and selected
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
      const res = await fetch(`http://localhost:8000/api/v1/restaurants/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("Delete failed");

      if (selectedRestaurant?.id === id) {
        setSelectedRestaurant(null);
      }
      fetchRestaurants();
    } catch (err) {
      console.error(err);
      alert("삭제 중 오류가 발생했습니다.");
    } finally {
      setConfirmDeleteId(null);
    }
  };

  const handleRefresh = async (id: string) => {
    setRefreshingId(id);
    try {
      const res = await fetch(`http://localhost:8000/api/v1/restaurants/${id}/refresh`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Refresh failed");

      const updated = await res.json();
      if (selectedRestaurant?.id === id) {
        setSelectedRestaurant(updated);
      }
      fetchRestaurants();
    } catch (err) {
      console.error(err);
      alert("정보 업데이트 중 오류가 발생했습니다.");
    } finally {
      setRefreshingId(null);
      setConfirmRefreshId(null);
    }
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

  const handleTouchStart = (e: React.TouchEvent) => {
    setTouchStart(e.targetTouches[0].clientY);
  };

  const handleTouchMove = (e: React.TouchEvent) => {
    setTouchEnd(e.targetTouches[0].clientY);
  };

  const handleTouchEnd = () => {
    if (!touchStart || !touchEnd) return;
    const distance = touchEnd - touchStart;
    const isSwipeDown = distance > 70; // Swipe down more than 70px
    if (isSwipeDown) {
      setSelectedRestaurant(null);
    }
    setTouchStart(null);
    setTouchEnd(null);
  };

  return (
    <main className="relative w-full h-screen overflow-hidden bg-white font-sans text-slate-900 flex flex-col md:flex-row">
      {/* Sidebar Area */}
      <aside className={`order-2 md:order-1 w-full md:w-[400px] bg-slate-50 border-t md:border-t-0 md:border-r border-slate-200 z-20 flex flex-col relative shadow-[0_-10px_30px_rgba(0,0,0,0.05)] md:shadow-none transition-all duration-300 ${isListVisible ? 'h-[50vh] md:h-full' : 'h-0 md:h-full'}`}>
        {/* Header */}
        <header className="p-6 bg-white border-b border-slate-100 flex-none z-10 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-black tracking-tight text-slate-900 mb-0.5 font-display uppercase italic">
              HIDDEN SPOT
            </h1>
            <p className="text-slate-400 text-[10px] font-bold uppercase tracking-widest leading-none">프리미엄 맛집 큐레이션</p>
          </div>
          <Badge className="bg-orange-500 hover:bg-orange-600 text-white text-[10px] font-black px-2 py-0.5 rounded-md border-none">BETA</Badge>
        </header>

        {/* Action Area (Desktop Only) */}
        <div className="p-4 flex-none hidden md:block">
          <AddUrlForm onAnalyze={(url) => { handleAnalyze(url); setIsRegisterOpen(false); }} isLoading={isLoading} />
        </div>

        {/* Scrollable List Area */}
        <ScrollArea className="flex-1 min-h-0 pb-10">
          <div className="space-y-5 py-4">
            {/* Search & Filter Controls (Desktop Only) */}
            <Card className="bg-white p-5 rounded-3xl border border-slate-200 shadow-sm hidden md:flex flex-col gap-4 mx-4">
              <div className="space-y-1.5 ">
                <label className="text-[10px] font-black uppercase text-slate-400 tracking-tighter">검색 키워드</label>
                <div className="relative group">
                  <Input
                    type="text"
                    placeholder="지역, 메뉴, 매장명..."
                    className="bg-slate-50 border-slate-100 rounded-xl h-12 text-sm focus-visible:ring-orange-500/10 focus-visible:border-orange-500 text-slate-900 placeholder:text-slate-300 transition-all pr-10"
                    value={searchKeyword}
                    onChange={(e) => handleSearchChange(e.target.value)}
                  />
                  {searchKeyword && (
                    <button
                      onClick={clearSearch}
                      className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-300 hover:text-slate-500 transition-colors p-1"
                    >
                      <X size={14} />
                    </button>
                  )}
                </div>
              </div>
              <div className="space-y-2">
                <div className="flex justify-between items-center">
                  <label className="text-[10px] font-black uppercase text-slate-400 tracking-tighter">최소 AI 점수</label>
                  <span className="text-[10px] font-black text-orange-600 bg-orange-50 px-2 py-0.5 rounded-full">{minScore}점+</span>
                </div>
                <input
                  type="range"
                  min="0"
                  max="90"
                  step="10"
                  value={minScore}
                  onChange={(e) => setMinScore(parseInt(e.target.value))}
                  className="w-full h-1.5 bg-slate-100 rounded-lg appearance-none cursor-pointer accent-orange-500"
                />
              </div>
            </Card>

            {/* Smart Category Chips - Carousel Style */}
            <div className="mb-2 relative group">
              {/* Left Arrow (Desktop) */}
              <button
                onClick={() => scrollCategories('left')}
                className="hidden md:flex absolute left-0 top-1/2 -translate-y-1/2 z-10 w-7 h-7 bg-white/90 backdrop-blur-sm border border-slate-200 rounded-full items-center justify-center text-slate-500 shadow-sm hover:bg-white hover:text-orange-500 hover:border-orange-200 transition-all -ml-2"
                aria-label="Previous categories"
              >
                <ChevronLeft size={14} strokeWidth={3} />
              </button>

              <div
                ref={categoryScrollRef}
                className="flex w-full overflow-x-auto gap-2 py-2 px-4 scroll-smooth no-scrollbar"
                style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
              >
                {SMART_CATEGORIES.map((cat) => (
                  <button
                    key={cat.id}
                    onClick={() => setSelectedCategory(cat.id)}
                    className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-[11px] font-black transition-all border whitespace-nowrap active:scale-95 shrink-0 ${selectedCategory === cat.id
                      ? 'bg-slate-900 border-slate-900 text-white shadow-md'
                      : 'bg-white border-slate-100 text-slate-500 hover:border-slate-200'
                      }`}
                  >
                    <span className="text-xs">{cat.icon}</span>
                    {cat.label}
                  </button>
                ))}
              </div>

              {/* Right Arrow (Desktop) */}
              <button
                onClick={() => scrollCategories('right')}
                className="hidden md:flex absolute right-0 top-1/2 -translate-y-1/2 z-10 w-7 h-7 bg-white/90 backdrop-blur-sm border border-slate-200 rounded-full items-center justify-center text-slate-500 shadow-sm hover:bg-white hover:text-orange-500 hover:border-orange-200 transition-all -mr-2"
                aria-label="Next categories"
              >
                <ChevronRight size={14} strokeWidth={3} />
              </button>
            </div>

            {/* List Label (Mobile Only) */}
            <div className="md:hidden flex items-center justify-between mb-2 px-4">
              <h2 className="text-[11px] font-black text-slate-400 uppercase tracking-widest">
                {selectedCategory !== 'all' ? SMART_CATEGORIES.find(c => c.id === selectedCategory)?.label : '저장된 맛집'} {filteredRestaurants.length}
              </h2>
            </div>

            {/* Loading Skeleton during analysis */}
            {isLoading && (
              <div className="space-y-3 animate-pulse opacity-50 px-4">
                <Skeleton className="h-24 w-full rounded-2xl bg-slate-200" />
                <Skeleton className="h-24 w-full rounded-2xl bg-slate-100" />
              </div>
            )}

            {/* Restaurant List */}
            <div className="flex flex-col gap-3 px-4">
              {sortedRestaurants.map((res) => (
                <div
                  key={res.id}
                  onClick={() => {
                    setSelectedRestaurant(res);
                    setIsListVisible(false);
                  }}
                  className={`group relative bg-white p-4 rounded-2xl border transition-all cursor-pointer hover:shadow-xl hover:-translate-y-1 hover:border-orange-200/50 ${selectedRestaurant?.id === res.id ? 'border-orange-500 ring-2 ring-orange-500/10 z-10' : 'border-slate-100'
                    }`}
                >
                  <div className="flex justify-between items-start gap-3">
                    <div className="flex-1 min-w-0">
                      <h3 className="font-black text-slate-800 text-[15px] leading-tight group-hover:text-orange-600 transition-colors uppercase tracking-tight truncate">{res.name}</h3>
                      <div className="flex flex-col gap-1.5 mt-2 overflow-hidden">
                        <div className="flex items-center gap-2">
                          <div className="flex items-center gap-1 text-[10px] font-bold text-slate-400 truncate">
                            <MapPin size={10} className="shrink-0" />
                            <span className="truncate">{res.address.split(' ').slice(0, 2).join(' ')}</span>
                          </div>
                          <span className="text-slate-200 text-[10px]">|</span>
                          <div className="flex items-center gap-1 text-[10px] font-bold text-emerald-600 truncate">
                            <Navigation size={10} className="shrink-0" />
                            <span className="truncate">{res.transport_info?.split(',')[0]}</span>
                          </div>
                        </div>

                        {/* Menu Preview */}
                        {res.must_eat_menus && res.must_eat_menus.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {res.must_eat_menus.slice(0, 2).map((menu: string) => (
                              <span key={menu} className="text-[9px] font-black px-1.5 py-0.5 bg-orange-50 text-orange-600 rounded-md border border-orange-100/50">
                                {menu}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0 ml-1">
                      <div className="flex items-center gap-0.5">
                        <button
                          onClick={(e) => { e.stopPropagation(); setConfirmRefreshId(res.id); }}
                          disabled={refreshingId === res.id}
                          className={`opacity-100 md:opacity-0 md:group-hover:opacity-100 p-1.5 text-slate-300 hover:text-orange-500 hover:bg-orange-50 rounded-lg transition-all ${refreshingId === res.id ? 'opacity-100' : ''}`}
                        >
                          <RefreshCw size={14} className={refreshingId === res.id ? "animate-spin text-orange-500" : ""} />
                        </button>
                        <button
                          onClick={(e) => { e.stopPropagation(); setConfirmDeleteId(res.id); }}
                          className="opacity-100 md:opacity-0 md:group-hover:opacity-100 p-1.5 text-slate-300 hover:text-red-500 hover:bg-red-50 rounded-lg transition-all"
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>

                      <div className={`w-8 h-8 rounded-lg text-[11px] font-black flex items-center justify-center shrink-0 shadow-sm ${res.ai_score >= 90 ? 'bg-emerald-500 text-white' :
                        res.ai_score >= 80 ? 'bg-orange-500 text-white' :
                          'bg-slate-200 text-slate-600'
                        }`}>
                        {res.ai_score}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </ScrollArea>
      </aside>

      {/* Map Area */}
      <section className="order-1 md:order-2 flex-1 relative bg-slate-100">
        {/* Mobile Map Search Header */}
        <div className="md:hidden absolute top-4 left-4 right-4 z-30 pointer-events-none">
          <div className="pointer-events-auto bg-white/90 backdrop-blur-xl border border-slate-200 rounded-2xl shadow-xl flex items-center px-4 h-12 ring-1 ring-black/5">
            <Search size={18} className="text-slate-400 mr-3" />
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
          onMarkerClick={(res) => {
            setSelectedRestaurant(res);
            setIsListVisible(false);
          }}
          onMapClick={() => {
            setSelectedRestaurant(null);
            setIsListVisible(false);
            setSearchKeyword("");
          }}
          onCenterChange={(lat, lng) => {
            setMapCenter({ lat, lng });
            if (!selectedRestaurant) {
              setUserMapCenter({ lat, lng });
            }
          }}
        />

        {/* Loading Overlay */}
        {isLoading && (
          <div className="absolute inset-0 bg-white/60 backdrop-blur-md z-50 flex flex-col items-center justify-center animate-in fade-in duration-500">
            <div className="relative">
              <div className="w-16 h-16 border-4 border-orange-100 rounded-full"></div>
              <div className="absolute top-0 left-0 w-16 h-16 border-4 border-orange-500 border-t-transparent rounded-full animate-spin"></div>
            </div>
            <p className="text-sm font-black tracking-widest text-slate-900 mt-6 uppercase">분석 중...</p>
            <p className="text-slate-400 text-[10px] font-bold mt-1 uppercase tracking-tighter">리뷰와 인사이트를 수집하고 있습니다...</p>
          </div>
        )}

        {/* Mobile Action Buttons (FABs) */}
        <div className="md:hidden absolute bottom-6 right-6 z-50 flex flex-col gap-3 items-end">
          <button
            onClick={() => setIsListVisible(!isListVisible)}
            className={`w-12 h-12 rounded-full shadow-lg flex items-center justify-center transition-all active:scale-90 ${isListVisible ? 'bg-orange-500 text-white' : 'bg-white border border-slate-200 text-slate-600'}`}
          >
            <List size={22} />
          </button>

          <Dialog open={isRegisterOpen} onOpenChange={setIsRegisterOpen}>
            <DialogTrigger asChild>
              <button className="w-14 h-14 bg-slate-900 rounded-full shadow-lg shadow-black/20 flex items-center justify-center text-white hover:bg-slate-800 transition-all active:scale-95">
                <Plus size={28} />
              </button>
            </DialogTrigger>
            <DialogContent className="sm:max-w-[425px] rounded-3xl p-0 bg-transparent border-none shadow-none">
              <DialogTitle className="sr-only">맛집 등록</DialogTitle>
              <DialogDescription className="sr-only">네이버 지도 링크를 입력하여 새로운 맛집을 분석하고 등록합니다.</DialogDescription>
              <AddUrlForm
                onAnalyze={(url) => { handleAnalyze(url); setIsRegisterOpen(false); }}
                isLoading={isLoading}
              />
            </DialogContent>
          </Dialog>
        </div>

        {/* Detail Card Overlay - Responsive */}
        {selectedRestaurant && (
          <div
            className="absolute inset-0 md:inset-auto md:bottom-8 md:right-8 z-[60] md:z-40 flex items-end md:items-initial"
            onTouchStart={handleTouchStart}
            onTouchMove={handleTouchMove}
            onTouchEnd={handleTouchEnd}
          >
            {/* Mobile Backdrop - Animated separately to fade in after/during modal slide */}
            <div
              className="md:hidden absolute inset-0 bg-slate-900/40 backdrop-blur-sm animate-in fade-in duration-700 delay-150 fill-mode-both"
              onClick={() => setSelectedRestaurant(null)}
            />

            <div className="relative w-full h-[90vh] md:h-auto md:w-[400px] bg-white md:bg-transparent overflow-y-auto custom-scrollbar rounded-t-[32px] md:rounded-3xl shadow-2xl transition-all pointer-events-auto animate-in slide-in-from-bottom-full duration-500 cubic-bezier(0.16, 1, 0.3, 1)">
              <div className="w-full max-w-md mx-auto h-full">
                <RestaurantCard
                  restaurant={selectedRestaurant}
                  onClose={() => setSelectedRestaurant(null)}
                />
              </div>
            </div>
          </div>
        )}
      </section>

      {/* Re-analysis Confirmation Modal */}
      <AlertDialog open={!!confirmRefreshId} onOpenChange={(open) => !open && setConfirmRefreshId(null)}>
        <AlertDialogContent className="rounded-3xl border-none p-6 bg-white shadow-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-xl font-black text-slate-900 uppercase tracking-tight">정보 업데이트</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-500 font-medium">
              최신 리뷰를 바탕으로 맛집 정보를 다시 분석할까요? <br />
              <span className="text-orange-600 font-bold mt-1 inline-block">(AI 분석에 약 10-20초가 소요됩니다)</span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="mt-4 gap-2">
            <AlertDialogCancel className="rounded-2xl border-slate-100 bg-slate-50 font-bold text-slate-600 h-12">취소</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => confirmRefreshId && handleRefresh(confirmRefreshId)}
              className="rounded-2xl bg-slate-900 hover:bg-slate-800 text-white font-bold h-12 px-6"
            >
              분석 시작
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>

      {/* Delete Confirmation Modal */}
      <AlertDialog open={!!confirmDeleteId} onOpenChange={(open) => !open && setConfirmDeleteId(null)}>
        <AlertDialogContent className="rounded-3xl border-none p-6 bg-white shadow-2xl">
          <AlertDialogHeader>
            <AlertDialogTitle className="text-xl font-black text-slate-900 uppercase tracking-tight">맛집 삭제</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-500 font-medium">
              이 맛집을 리스트에서 정말 삭제하시겠습니까? <br />
              <span className="text-red-500 font-bold mt-1 inline-block">삭제된 데이터는 복구할 수 없습니다.</span>
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter className="mt-4 gap-2">
            <AlertDialogCancel className="rounded-2xl border-slate-100 bg-slate-50 font-bold text-slate-600 h-12">취소</AlertDialogCancel>
            <AlertDialogAction
              onClick={() => confirmDeleteId && handleDelete(confirmDeleteId)}
              className="rounded-2xl bg-red-500 hover:bg-red-600 text-white font-bold h-12 px-6"
            >
              삭제하기
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </main>
  );
}
