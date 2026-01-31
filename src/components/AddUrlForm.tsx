import { useState } from "react";
import { Link2, Sparkles, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

interface AddUrlFormProps {
    onAnalyze: (url: string) => void;
    isLoading: boolean;
}

export default function AddUrlForm({ onAnalyze, isLoading }: AddUrlFormProps) {
    const [url, setUrl] = useState("");

    const handleSubmit = (e: React.FormEvent) => {
        e.preventDefault();
        if (url.trim()) {
            onAnalyze(url);
            setUrl("");
        }
    };

    return (
        <Card className="border-slate-200 shadow-sm transition-all hover:shadow-md rounded-3xl overflow-hidden">
            <CardHeader className="flex flex-row items-center gap-2 p-5 pb-0 space-y-0">
                <div className="bg-orange-100 p-1.5 rounded-xl">
                    <Sparkles size={16} className="text-orange-600" />
                </div>
                <CardTitle className="text-sm font-black text-slate-800 uppercase tracking-widest">맛집 등록</CardTitle>
            </CardHeader>

            <CardContent className="p-5 overflow-visible">
                <form onSubmit={handleSubmit} className="flex flex-col gap-3">
                    <div className="relative group">
                        <Textarea
                            value={url}
                            onChange={(e) => setUrl(e.target.value)}
                            placeholder="네이버 지도 URL 또는 네이버 공유 시 복사된 내용을  붙여넣으세요"
                            className="bg-slate-50 border-slate-200 rounded-2xl p-4 text-sm text-slate-900 placeholder:text-slate-400 focus-visible:ring-orange-500/20 focus-visible:border-orange-500 min-h-[100px] resize-none transition-all pr-10"
                            disabled={isLoading}
                        />
                        <Link2 size={16} className="absolute top-4 right-4 text-slate-300 group-focus-within:text-orange-400 transition-colors" />
                    </div>

                    <Button
                        type="submit"
                        disabled={isLoading || !url.trim()}
                        className="w-full bg-slate-900 hover:bg-slate-800 text-white font-bold h-12 rounded-2xl transition-all"
                    >
                        {isLoading ? (
                            <>
                                <Loader2 size={18} className="animate-spin text-orange-500" />
                                <span className="text-sm font-bold">AI 분석 중...</span>
                            </>
                        ) : (
                            <>
                                <span className="text-sm font-bold">분석 및 저장</span>
                                <Sparkles size={14} className="ml-1 text-orange-400" />
                            </>
                        )}
                    </Button>
                </form>
            </CardContent>
        </Card>
    );
}

