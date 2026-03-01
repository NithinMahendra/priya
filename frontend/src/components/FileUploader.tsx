import type { ChangeEvent } from "react";

interface FileUploaderProps {
  onCodeLoaded: (fileName: string, content: string) => void;
}

export function FileUploader({ onCodeLoaded }: FileUploaderProps): JSX.Element {
  const handleUpload = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    const content = await file.text();
    onCodeLoaded(file.name, content);
    event.target.value = "";
  };

  return (
    <label className="inline-flex cursor-pointer items-center rounded-xl border border-app-border bg-app-panelSoft px-4 py-2 text-sm text-app-text transition hover:border-app-accent hover:text-white">
      Upload File
      <input type="file" className="hidden" onChange={handleUpload} />
    </label>
  );
}
