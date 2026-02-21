"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";

interface MapProps {
    restaurants: any[];
    selectedId?: string;
    onMarkerClick: (restaurant: any) => void;
    onMapClick?: () => void;
    onCenterChange?: (lat: number, lng: number) => void;
    onBoundsChange?: (bounds: { north: number; south: number; east: number; west: number }) => void;
    initialCenter?: { lat: number; lng: number };
}

declare global {
    interface Window {
        naver: any;
        navermap_authFailure?: () => void;
    }
}

const DEFAULT_CENTER = { lat: 37.547241, lng: 127.047325 };

export default function Map({
    restaurants,
    selectedId,
    onMarkerClick,
    onMapClick,
    onCenterChange,
    onBoundsChange,
    initialCenter,
}: MapProps) {
    const clientId = process.env.NEXT_PUBLIC_NAVER_MAPS_CLIENT_ID;
    const mapKeyMissing = !clientId;
    const mapRef = useRef<HTMLDivElement>(null);
    const [map, setMap] = useState<any>(null);
    const [mapError, setMapError] = useState<string | null>(null);
    const markersRef = useRef<any[]>([]);
    const scriptPromiseRef = useRef<Promise<void> | null>(null);
    const onMapClickRef = useRef(onMapClick);
    const onCenterChangeRef = useRef(onCenterChange);
    const onBoundsChangeRef = useRef(onBoundsChange);
    const onMarkerClickRef = useRef(onMarkerClick);

    useEffect(() => {
        onMapClickRef.current = onMapClick;
        onCenterChangeRef.current = onCenterChange;
        onBoundsChangeRef.current = onBoundsChange;
        onMarkerClickRef.current = onMarkerClick;
    }, [onMapClick, onCenterChange, onBoundsChange, onMarkerClick]);

    useEffect(() => {
        if (mapKeyMissing || map) return;

        const initMap = async () => {
            if (window.naver?.maps) return;
            if (!scriptPromiseRef.current) {
                scriptPromiseRef.current = new Promise<void>((resolve, reject) => {
                    const existing = document.querySelector<HTMLScriptElement>("script[data-naver-map-sdk='1']");
                    if (existing) {
                        existing.addEventListener("load", () => resolve(), { once: true });
                        existing.addEventListener("error", () => reject(new Error("sdk-load-failed")), { once: true });
                        return;
                    }

                    const script = document.createElement("script");
                    script.src = `https://openapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${clientId}&submodules=geocoder`;
                    script.async = true;
                    script.dataset.naverMapSdk = "1";
                    script.onload = () => resolve();
                    script.onerror = () => reject(new Error("sdk-load-failed"));
                    document.head.appendChild(script);
                });
            }
            await scriptPromiseRef.current;
        };

        const mountMap = async () => {
            try {
                window.navermap_authFailure = () => {
                    setMapError("네이버 지도 인증에 실패했습니다. NCP 콘솔의 웹 서비스 URL(Referer) 설정을 확인해 주세요.");
                };
                await initMap();
            } catch {
                setMapError("네이버 지도 스크립트를 로드하지 못했습니다. 도메인 허용 설정을 확인해 주세요.");
                return;
            }

            if (!mapRef.current || !window.naver?.maps) {
                setMapError("네이버 지도 SDK를 초기화하지 못했습니다.");
                return;
            }

            const mapInstance = new window.naver.maps.Map(mapRef.current, {
                center: new window.naver.maps.LatLng(initialCenter?.lat ?? DEFAULT_CENTER.lat, initialCenter?.lng ?? DEFAULT_CENTER.lng),
                zoom: 14,
                logoControl: false,
                mapDataControl: false,
                scaleControl: true,
            });

            setMap(mapInstance);

            window.naver.maps.Event.addListener(mapInstance, "click", () => {
                if (onMapClickRef.current) onMapClickRef.current();
            });

            window.naver.maps.Event.addListener(mapInstance, "idle", () => {
                const center = mapInstance.getCenter();
                if (onCenterChangeRef.current) onCenterChangeRef.current(center.lat(), center.lng());
                const bounds = mapInstance.getBounds();
                if (bounds && onBoundsChangeRef.current) {
                    const ne = bounds.getNE();
                    const sw = bounds.getSW();
                    onBoundsChangeRef.current({
                        north: ne.lat(),
                        south: sw.lat(),
                        east: ne.lng(),
                        west: sw.lng(),
                    });
                }
            });
        };
        mountMap();
    }, [clientId, mapKeyMissing, map, initialCenter]);

    const validRestaurants = useMemo(
        () =>
            Array.isArray(restaurants)
                ? restaurants.filter((r) => Number.isFinite(Number(r?.latitude)) && Number.isFinite(Number(r?.longitude)))
                : [],
        [restaurants],
    );

    useEffect(() => {
        if (!map || !selectedId || validRestaurants.length === 0) return;
        const selected = validRestaurants.find(res => res.id === selectedId);
        if (selected) {
            map.panTo(new window.naver.maps.LatLng(selected.latitude, selected.longitude));
        }
    }, [map, selectedId, validRestaurants]);

    useEffect(() => {
        if (!map) return;

        markersRef.current.forEach((marker) => marker.setMap(null));
        markersRef.current = [];

        validRestaurants.forEach((res) => {
            const isSelected = res.id === selectedId;
            const markerColor = isSelected ? '#f97316' : '#0f172a';
            const markerSize = isSelected ? 36 : 28;

            const markerContent = `
                <div style="cursor:pointer; width:${markerSize}px; height:${markerSize}px; background:${markerColor}; border:2.5px solid white; border-radius:50% 50% 50% 0; transform:rotate(-45deg); box-shadow:0 4px 12px rgba(0,0,0,0.25); display:flex; align-items:center; justify-content:center; transition: all 0.2s ease;">
                    <div style="width:8px; height:8px; background:white; border-radius:50%; transform:rotate(45deg);"></div>
                </div>
            `;

            const marker = new window.naver.maps.Marker({
                position: new window.naver.maps.LatLng(res.latitude, res.longitude),
                map: map,
                icon: {
                    content: markerContent,
                    anchor: new window.naver.maps.Point(markerSize / 2, markerSize)
                },
                zIndex: isSelected ? 100 : 1,
            });

            window.naver.maps.Event.addListener(marker, "click", () => {
                onMarkerClickRef.current(res);
                map.panTo(new window.naver.maps.LatLng(res.latitude, res.longitude));
            });

            markersRef.current.push(marker);
        });
    }, [map, validRestaurants, selectedId]);

    useEffect(() => {
        if (!mapKeyMissing || !onCenterChangeRef.current) return;
        onCenterChangeRef.current(initialCenter?.lat ?? DEFAULT_CENTER.lat, initialCenter?.lng ?? DEFAULT_CENTER.lng);
    }, [mapKeyMissing, initialCenter]);

    const resolvedMapError = mapKeyMissing ? "Map key missing. Set NEXT_PUBLIC_NAVER_MAPS_CLIENT_ID." : mapError;

    return (
        <div className="w-full h-full relative">
            <div ref={mapRef} className="w-full h-full" />
            {!resolvedMapError && !map && (
                <div className="absolute inset-0 flex items-center justify-center bg-slate-100/80">
                    <p className="text-xs font-bold text-slate-500">지도 로딩 중...</p>
                </div>
            )}
            {resolvedMapError && (
                <div className="absolute inset-0 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center p-6 z-10">
                    <div className="max-w-lg bg-white text-slate-900 rounded-2xl p-5 shadow-2xl border border-slate-200">
                        <div className="flex items-start gap-3">
                            <AlertTriangle className="text-amber-500 shrink-0 mt-0.5" size={20} />
                            <div>
                                <p className="font-bold text-sm">네이버 지도를 불러오지 못했습니다.</p>
                                <p className="text-sm text-slate-600 mt-1">{resolvedMapError}</p>
                                <p className="text-xs text-slate-500 mt-3">
                                    Netlify 환경변수 `NEXT_PUBLIC_NAVER_MAPS_CLIENT_ID`와 네이버 클라우드 플랫폼의 Referer 도메인 허용 목록을 확인해 주세요.
                                </p>
                            </div>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
