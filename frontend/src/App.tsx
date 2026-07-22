import { useCallback, useEffect, useState } from "react";
import type { JSX } from "react";

type Root = { id: string; status: string; current_generation: number };
type Entry = { id: number; name: string; kind: "file" | "directory"; size_bytes: number };
type Job = { id: string; state: string; attempts: number; error_code: string | null };

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, init);
  if (!response.ok) throw new Error("请求未完成");
  return response.json() as Promise<T>;
}

export function App(): JSX.Element {
  const [roots, setRoots] = useState<Root[]>([]);
  const [entries, setEntries] = useState<Entry[]>([]);
  const [jobs, setJobs] = useState<Job[]>([]);
  const [message, setMessage] = useState("正在读取本地索引状态…");

  const refresh = useCallback(async () => {
    try {
      const [nextRoots, nextEntries, nextJobs] = await Promise.all([
        request<Root[]>("/api/v1/roots"),
        request<{ items: Entry[] }>("/api/v1/entries"),
        request<Job[]>("/api/v1/jobs"),
      ]);
      setRoots(nextRoots); setEntries(nextEntries.items); setJobs(nextJobs); setMessage("本地索引已连接");
    } catch { setMessage("暂时无法读取索引状态"); }
  }, []);

  useEffect(() => { void refresh(); }, [refresh]);

  const scan = async (): Promise<void> => {
    try {
      await request("/api/v1/roots/default/scan", { method: "POST" });
      setMessage("扫描任务已加入队列");
      await refresh();
    } catch { setMessage("无法创建扫描任务"); }
  };

  return <main className="shell"><section className="panel" aria-labelledby="app-title">
    <header><p className="brand">AI NAS Search</p><h1 id="app-title">文件浏览与扫描</h1><p>{message}</p></header>
    <div className="toolbar"><button type="button" onClick={() => void scan()}>开始扫描</button><button className="secondary" type="button" onClick={() => void refresh()}>刷新</button></div>
    <section className="grid" aria-label="索引状态"><div><span>数据源</span><strong>{roots[0]?.status ?? "未知"}</strong></div><div><span>扫描代次</span><strong>{roots[0]?.current_generation ?? 0}</strong></div><div><span>任务</span><strong>{jobs.length}</strong></div></section>
    <section className="content"><div><h2>根目录</h2><ul>{roots.map((root) => <li key={root.id}>{root.id}<small>{root.status}</small></li>)}</ul></div><div><h2>文件</h2><ul>{entries.length ? entries.map((entry) => <li key={entry.id}>{entry.name}<small>{entry.kind === "directory" ? "目录" : `${entry.size_bytes} B`}</small></li>) : <li>尚未建立索引</li>}</ul></div><div><h2>任务队列</h2><ul>{jobs.length ? jobs.map((job) => <li key={job.id}>{job.state}<small>尝试 {job.attempts}</small></li>) : <li>暂无任务</li>}</ul></div></section>
  </section></main>;
}
