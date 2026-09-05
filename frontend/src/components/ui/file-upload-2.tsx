"use client";

import * as React from "react";
import {
  FileSpreadsheetIcon,
  Upload01Icon,
} from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { BorderBeam } from "border-beam";

import { Card } from "./card";

/* ---------------------------------------------------------
   Simple className utility
   --------------------------------------------------------- */
function cn(
  ...classes: Array<string | false | null | undefined>
) {
  return classes.filter(Boolean).join(" ");
}

/* ---------------------------------------------------------
   Types
   --------------------------------------------------------- */

type FileUploadItem = {
  id: string;
  name: string;
  type: string;
  size: number;
  url: string;
};

type AcceptedFileType = {
  label: string;
  icon: React.ComponentProps<typeof HugeiconsIcon>["icon"];
};

type FileUploadProps = {
  accept?: string;
  acceptedFileTypes?: AcceptedFileType[];
  borderBeamTheme?: React.ComponentProps<typeof BorderBeam>["theme"];
  browseLabel?: string;
  className?: string;
  description?: string;
  draggingLabel?: string;
  multiple?: boolean;
  showBorderBeam?: boolean;
  showFileList?: boolean;
  title?: string;

  onFilesAccepted?: (files: File[]) => void;
  onFilesChange?: (files: FileUploadItem[]) => void;
};

/* ---------------------------------------------------------
   Accepted file types
   --------------------------------------------------------- */

const ACCEPTED_FILE_TYPES: AcceptedFileType[] = [
  {
    label: "CSV",
    icon: FileSpreadsheetIcon,
  },
];

const DEFAULT_ACCEPT = ".csv,text/csv";

/* ---------------------------------------------------------
   Icon animation
   --------------------------------------------------------- */

const ICON_TRANSFORMS = [
  {
    idle: "translate(-78%, -50%) rotate(-8deg)",
    active:
      "translate(-114%, -50%) rotate(-12deg) scale(1.08)",
  },
  {
    idle: "translate(-50%, -50%) rotate(0deg)",
    active:
      "translate(-50%, -50%) rotate(0deg) scale(1.18)",
  },
  {
    idle: "translate(-22%, -50%) rotate(8deg)",
    active:
      "translate(14%, -50%) rotate(12deg) scale(1.08)",
  },
];

/* ---------------------------------------------------------
   Helpers
   --------------------------------------------------------- */

function formatBytes(bytes: number) {
  if (bytes === 0) return "0 B";

  const units = ["B", "KB", "MB", "GB"];

  const index = Math.min(
    Math.floor(Math.log(bytes) / Math.log(1024)),
    units.length - 1,
  );

  return `${(bytes / 1024 ** index).toFixed(
    index === 0 ? 0 : 1,
  )} ${units[index]}`;
}

function matchesAccept(
  file: File,
  accept?: string,
) {
  if (!accept) return true;

  return accept.split(",").some((rawToken) => {
    const token = rawToken.trim().toLowerCase();

    if (!token) return false;

    if (token.startsWith(".")) {
      return file.name
        .toLowerCase()
        .endsWith(token);
    }

    if (token.endsWith("/*")) {
      return file.type
        .toLowerCase()
        .startsWith(token.slice(0, -1));
    }

    return (
      file.type.toLowerCase() === token
    );
  });
}

function toUploadItems(
  files: FileList | File[],
): FileUploadItem[] {
  return Array.from(files).map((file) => ({
    id: `${file.name}-${file.size}-${file.lastModified}`,
    name: file.name,
    type: file.type || "text/csv",
    size: file.size,
    url: URL.createObjectURL(file),
  }));
}

/* ---------------------------------------------------------
   Upload icon cluster
   --------------------------------------------------------- */

function UploadIconCluster({
  acceptedFileTypes,
  isDragging,
}: {
  acceptedFileTypes: AcceptedFileType[];
  isDragging: boolean;
}) {
  const singleIcon =
    acceptedFileTypes.length === 1;

  return (
    <div className="relative h-16 w-40">
      {acceptedFileTypes.map(
        (item, index) => (
          <Card
            key={item.label}
            className={cn(
              "absolute left-1/2 top-1/2 grid size-12 place-items-center rounded-xl bg-background text-muted-foreground transition-[transform,color,background-color] duration-500 ease-[cubic-bezier(0.22,1,0.36,1)]",
              "motion-reduce:transition-none",
              index === 1 && "z-10",
              isDragging &&
                "bg-popover text-foreground shadow-md shadow-black/10",
            )}
            style={{
              transform: singleIcon
                ? `translate(-50%, -50%) scale(${
                    isDragging ? 1.14 : 1
                  })`
                : isDragging
                  ? ICON_TRANSFORMS[index]
                      ?.active
                  : ICON_TRANSFORMS[index]
                      ?.idle,
            }}
          >
            <HugeiconsIcon
              icon={item.icon}
              className="size-5"
            />
          </Card>
        ),
      )}
    </div>
  );
}

/* ---------------------------------------------------------
   Main File Upload component
   --------------------------------------------------------- */

export function FileUpload({
  accept = DEFAULT_ACCEPT,
  acceptedFileTypes =
    ACCEPTED_FILE_TYPES,
  borderBeamTheme = "light",
  browseLabel = "Browse CSV files",
  className,
  description = "Select all 3 required CSV files together",
  draggingLabel = "Drop all 3 files here",
  multiple = true,
  showBorderBeam = true,
  showFileList = false,
  title = "Upload your 3 reconciliation files",
  onFilesAccepted,
  onFilesChange,
}: FileUploadProps) {
  const dragDepthRef =
    React.useRef(0);

  const inputRef =
    React.useRef<HTMLInputElement>(null);

  const [isDragging, setIsDragging] =
    React.useState(false);

  const [files, setFiles] =
    React.useState<FileUploadItem[]>([]);

  const [rejectionMessage, setRejectionMessage] =
    React.useState<string | null>(null);

  /* -------------------------------------------------------
     Handle selected files
     ------------------------------------------------------- */

  const commitFiles = React.useCallback(
    (nextFiles: FileList | File[]) => {
      const acceptedFiles =
        Array.from(nextFiles).filter(
          (file) =>
            matchesAccept(file, accept),
        );

      if (acceptedFiles.length === 0) {
        setRejectionMessage(
          "Only CSV files are supported.",
        );
        return;
      }

      /*
       * This upload component is designed
       * for the three reconciliation files.
       */
      if (acceptedFiles.length < 3) {
        setRejectionMessage(
          `Please select all 3 required CSV files. ${acceptedFiles.length}/3 selected.`,
        );
      } else {
        setRejectionMessage(null);
      }

      onFilesAccepted?.(
        acceptedFiles,
      );

      const items =
        toUploadItems(acceptedFiles);

      setFiles(
        (previousFiles) => {
          previousFiles.forEach(
            (file) =>
              URL.revokeObjectURL(
                file.url,
              ),
          );

          return items;
        },
      );

      onFilesChange?.(items);
    },
    [
      accept,
      onFilesAccepted,
      onFilesChange,
    ],
  );

  /* -------------------------------------------------------
     Cleanup object URLs
     ------------------------------------------------------- */

  React.useEffect(() => {
    return () => {
      files.forEach((file) =>
        URL.revokeObjectURL(
          file.url,
        ),
      );
    };
  }, [files]);

  /* -------------------------------------------------------
     Open browser file selector
     ------------------------------------------------------- */

  const openFileDialog =
    React.useCallback(() => {
      inputRef.current?.click();
    }, []);

  /* -------------------------------------------------------
     Dropzone
     ------------------------------------------------------- */

  const dropzone = (
    <div
      role="button"
      tabIndex={0}
      className={cn(
        "relative flex min-h-[280px] cursor-pointer flex-col items-center justify-center gap-5 overflow-hidden rounded-[1.125rem] border border-dashed bg-background px-6 py-10 text-center transition-all duration-200",
        "motion-reduce:transition-none",

        isDragging
          ? "scale-[1.01] border-primary/50 bg-primary/5"
          : "border-foreground/15 hover:border-primary/40 hover:bg-muted/30",
      )}
      onClick={openFileDialog}
      onDragEnter={(event) => {
        event.preventDefault();

        dragDepthRef.current += 1;
        setIsDragging(true);
      }}
      onDragLeave={(event) => {
        event.preventDefault();

        dragDepthRef.current =
          Math.max(
            0,
            dragDepthRef.current - 1,
          );

        if (
          dragDepthRef.current === 0
        ) {
          setIsDragging(false);
        }
      }}
      onDragOver={(event) => {
        event.preventDefault();
      }}
      onDrop={(event) => {
        event.preventDefault();

        dragDepthRef.current = 0;
        setIsDragging(false);

        if (
          event.dataTransfer.files
            .length > 0
        ) {
          commitFiles(
            event.dataTransfer.files,
          );
        }
      }}
      onKeyDown={(event) => {
        if (
          event.key === "Enter" ||
          event.key === " "
        ) {
          event.preventDefault();
          openFileDialog();
        }
      }}
    >
      {/* Upload animation */}
      <UploadIconCluster
        acceptedFileTypes={
          acceptedFileTypes
        }
        isDragging={isDragging}
      />

      {/* Main text */}
      <div className="space-y-1.5">
        <div className="text-base font-semibold text-ink">
          {isDragging
            ? draggingLabel
            : title}
        </div>

        <div className="text-sm text-muted-foreground">
          {description}
        </div>

        {rejectionMessage && (
          <div className="pt-1 text-xs font-medium text-destructive">
            {rejectionMessage}
          </div>
        )}
      </div>

      {/* Browse button */}
      <div
        className={cn(
          "inline-flex items-center gap-2 rounded-full border bg-background px-4 py-2 text-xs font-medium text-muted-foreground transition",

          isDragging &&
            "border-primary/30 bg-primary/5 text-primary",
        )}
      >
        <HugeiconsIcon
          icon={Upload01Icon}
          className="size-3.5"
        />

        <span>
          {isDragging
            ? draggingLabel
            : browseLabel}
        </span>
      </div>

      {/* Required files */}
      <div className="flex flex-wrap justify-center gap-2 text-[11px] text-muted-foreground">
        <span className="rounded-full bg-muted px-2.5 py-1">
          01 · Ledger
        </span>

        <span className="rounded-full bg-muted px-2.5 py-1">
          02 · Settlement
        </span>

        <span className="rounded-full bg-muted px-2.5 py-1">
          03 · Bank
        </span>
      </div>

      {/* Hidden input */}
      <input
        ref={inputRef}
        type="file"
        accept={accept}
        multiple={multiple}
        className="hidden"
        onChange={(event) => {
          if (event.target.files) {
            commitFiles(
              event.target.files,
            );

            event.currentTarget.value =
              "";
          }
        }}
      />
    </div>
  );

  /* -------------------------------------------------------
     Render
     ------------------------------------------------------- */

  return (
    <div
      className={cn(
        "space-y-3",
        className,
      )}
    >
      {showBorderBeam ? (
        <BorderBeam
          active={isDragging}
          borderRadius={18}
          brightness={2.4}
          className="rounded-[1.125rem]"
          colorVariant="ocean"
          duration={2.4}
          size="md"
          strength={1}
          theme={borderBeamTheme}
        >
          {dropzone}
        </BorderBeam>
      ) : (
        dropzone
      )}

      {/* Selected file list */}
      {showFileList &&
        files.length > 0 && (
          <div className="rounded-xl border bg-background">
            {files.map((file) => (
              <div
                key={file.id}
                className="flex items-center gap-3 border-b px-3 py-2.5 last:border-b-0"
              >
                <div className="grid size-10 shrink-0 place-items-center rounded-lg bg-muted text-muted-foreground">
                  <HugeiconsIcon
                    icon={
                      FileSpreadsheetIcon
                    }
                    className="size-5"
                  />
                </div>

                <div className="min-w-0 flex-1">
                  <div className="truncate text-sm font-medium">
                    {file.name}
                  </div>

                  <div className="truncate text-xs text-muted-foreground">
                    CSV ·{" "}
                    {formatBytes(
                      file.size,
                    )}
                  </div>
                </div>

                <div className="rounded-full bg-fin-100 px-2 py-1 text-xs font-medium text-fin-600">
                  Ready
                </div>
              </div>
            ))}
          </div>
        )}
    </div>
  );
}

export default FileUpload;