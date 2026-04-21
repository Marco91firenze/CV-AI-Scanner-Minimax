import fs from "fs/promises";
import path from "path";
import ReactMarkdown from "react-markdown";
import { DpaAcceptButton } from "./DpaAcceptButton";

export default async function DpaPage() {
  const mdPath = path.join(process.cwd(), "content", "legal", "DPA.md");
  const src = await fs.readFile(mdPath, "utf8");

  return (
    <div className="mx-auto max-w-3xl px-4 py-12">
      <article className="prose prose-slate max-w-none prose-headings:font-semibold prose-a:text-brand-700">
        <ReactMarkdown>{src}</ReactMarkdown>
      </article>
      <DpaAcceptButton />
    </div>
  );
}
