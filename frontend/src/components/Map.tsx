"use client";

import { useEffect, useRef, useState } from "react";
import { Navigation } from "lucide-react";

interface MapProps {
    restaurants: any[];
    selectedId?: string;
    onMarkerClick: (restaurant: any) => void;
    onMapClick?: () => void;
    onCenterChange?: (lat: number, lng: number) => void;
}

declare global {
    interface Window {
        naver: any;
        navermap_authFailure?: () => void;
    }
}

export default function Map({ restaurants, selectedId, onMarkerClick, onMapClick, onCenterChange }: MapProps) {
    const mapRef = useRef<HTMLDivElement>(null);
    const [map, setMap] = useState<any>(null);

    useEffect(() => {
        const clientId = process.env.NEXT_PUBLIC_NAVER_MAPS_CLIENT_ID;
        if (!clientId) return;

        const script = document.createElement("script");
        script.src = `https://openapi.map.naver.com/openapi/v3/maps.js?ncpKeyId=${clientId}&submodules=geocoder`;
        script.async = true;

        window.navermap_authFailure = () => {
            console.error("Naver Maps authentication failed.");
        };

        script.onload = () => {
            if (mapRef.current) {
                const mapInstance = new window.naver.maps.Map(mapRef.current, {
                    center: new window.naver.maps.LatLng(37.5665, 126.9780),
                    zoom: 14,
                    logoControl: false,
                    mapDataControl: false,
                    scaleControl: true,
                });

                setMap(mapInstance);

                window.naver.maps.Event.addListener(mapInstance, 'click', () => {
                    if (onMapClick) onMapClick();
                });

                window.naver.maps.Event.addListener(mapInstance, 'idle', () => {
                    const center = mapInstance.getCenter();
                    if (onCenterChange) onCenterChange(center.lat(), center.lng());
                });
            }
        };
        document.head.appendChild(script);

        return () => {
            document.head.removeChild(script);
        };
    }, []);

    const markersRef = useRef<any[]>([]);

    useEffect(() => {
        if (!map || !restaurants || !selectedId) return;

        const selected = restaurants.find(res => res.id === selectedId);
        if (selected) {
            map.panTo(new window.naver.maps.LatLng(selected.latitude, selected.longitude));
        }
    }, [map, selectedId, restaurants]);

    useEffect(() => {
        if (!map || !restaurants) return;

        markersRef.current.forEach((marker) => marker.setMap(null));
        markersRef.current = [];

        restaurants.forEach((res) => {
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
                onMarkerClick(res);
                map.panTo(new window.naver.maps.LatLng(res.latitude, res.longitude));
            });

            markersRef.current.push(marker);
        });
    }, [map, restaurants, selectedId]);

    return (
        <div className="w-full h-full relative">
            <div ref={mapRef} className="w-full h-full" />
        </div>
    );
}
