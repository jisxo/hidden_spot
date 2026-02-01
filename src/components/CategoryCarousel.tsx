"use client";

import React, { useRef } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";

interface Category {
    id: string;
    label: string;
    icon: string;
}

interface CategoryCarouselProps {
    categories: Category[];
    selectedCategory: string;
    onSelectCategory: (id: string) => void;
}

export default function CategoryCarousel({
    categories,
    selectedCategory,
    onSelectCategory,
}: CategoryCarouselProps) {
    const scrollRef = useRef<HTMLDivElement>(null);

    const scroll = (direction: 'left' | 'right') => {
        if (scrollRef.current) {
            const scrollAmount = 200;
            scrollRef.current.scrollBy({
                left: direction === 'right' ? scrollAmount : -scrollAmount,
                behavior: 'smooth'
            });
        }
    };

    return (
        <div className="relative group/carousel">
            {/* Left Arrow */}
            <button
                onClick={() => scroll('left')}
                className="hidden md:flex absolute left-0 top-1/2 -translate-y-1/2 z-10 w-8 h-8 bg-white/90 backdrop-blur-sm border border-slate-200 rounded-full items-center justify-center text-slate-500 shadow-sm hover:bg-white hover:text-orange-500 hover:border-orange-200 transition-all -ml-2 opacity-0 group-hover/carousel:opacity-100"
                aria-label="Previous categories"
            >
                <ChevronLeft size={16} strokeWidth={3} />
            </button>

            {/* Categories Scroll Area */}
            <div
                ref={scrollRef}
                className="flex w-full overflow-x-auto gap-2 py-2 px-4 scroll-smooth no-scrollbar"
                style={{ scrollbarWidth: 'none', msOverflowStyle: 'none' }}
            >
                {categories.map((cat) => (
                    <button
                        key={cat.id}
                        onClick={() => onSelectCategory(cat.id)}
                        className={`flex items-center gap-2 px-4 py-2.5 rounded-full text-[11px] font-black transition-all border whitespace-nowrap active:scale-95 shrink-0 ${selectedCategory === cat.id
                                ? 'bg-slate-900 border-slate-900 text-white shadow-md'
                                : 'bg-white border-slate-100 text-slate-500 hover:border-slate-300'
                            }`}
                    >
                        <span className="text-sm">{cat.icon}</span>
                        {cat.label}
                    </button>
                ))}
            </div>

            {/* Right Arrow */}
            <button
                onClick={() => scroll('right')}
                className="hidden md:flex absolute right-0 top-1/2 -translate-y-1/2 z-10 w-8 h-8 bg-white/90 backdrop-blur-sm border border-slate-200 rounded-full items-center justify-center text-slate-500 shadow-sm hover:bg-white hover:text-orange-500 hover:border-orange-200 transition-all -mr-2 opacity-0 group-hover/carousel:opacity-100"
                aria-label="Next categories"
            >
                <ChevronRight size={16} strokeWidth={3} />
            </button>
        </div>
    );
}
