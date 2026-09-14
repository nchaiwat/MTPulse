import { useState } from "react";
import { AlertTriangle, Building2, CheckCircle2 } from "lucide-react";
import {
  confirmTaImport,
  previewTaImport,
  type TaImportPreview,
  type UploadProgress,
} from "./importApi";
import { formatDisplayDate } from "../../shared/dateFormat";

const number = new Intl.NumberFormat("th-TH", { maximumFractionDigits: 2 });

export function TaImportPanel({ onCompleted }: { onCompleted: () => void }) {
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<TaImportPreview | null>(null);
  const [busy, setBusy] = useState<"preview" | "confirm" | null>(null);
  const [progress, setProgress] = useState<UploadProgress | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const inspect = async () => {
    if (!file) return;
    setBusy("preview");
    setMessage(null);
    setPreview(null);
    try {
      setPreview(await previewTaImport(file, setProgress));
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "ตรวจสอบไฟล์ Thai-Aust ไม่สำเร็จ",
      );
      onCompleted();
    } finally {
      setProgress(null);
      setBusy(null);
    }
  };

  const confirm = async () => {
    if (!file || !preview?.canImport) return;
    setBusy("confirm");
    setMessage(null);
    try {
      const result = await confirmTaImport(
        file,
        preview.businessFingerprint,
        setProgress,
      );
      setMessage(result.message);
      setFile(null);
      setPreview(null);
      onCompleted();
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "นำเข้าข้อมูล Thai-Aust ไม่สำเร็จ",
      );
      onCompleted();
    } finally {
      setProgress(null);
      setBusy(null);
    }
  };

  return (
    <section
      id="import-panel-TA"
      className="import-workflow import-hp-mh-workflow"
      role="tabpanel"
      aria-labelledby="import-tab-TA"
    >
      <header className="import-workflow-heading">
        <div>
          <span className="eyebrow">TA manual import</span>
          <h2>Thai-Aust (TA)</h2>
        </div>
        <span className="import-format-note">Daily · Runglawan .xlsx</span>
      </header>
      <div className="hp-mh-source-note">
        <Building2 size={18} aria-hidden="true" />
        <p>
          ระบบอ่านวันที่จากชื่อไฟล์ Runglawan แล้วลบ 1 วันเป็นวันที่ข้อมูล
          โดยวันที่ข้อมูลคือวันก่อนหน้า 1 วัน และเก็บ SKU
          เป็นข้อความโดยไม่บังคับรูปแบบ
        </p>
      </div>
      <div className="hp-mh-file-grid">
        <label>
          <span>1 · Runglawan-YYYY-MM-DD*.xlsx</span>
          <input
            type="file"
            accept=".xlsx"
            disabled={busy !== null}
            onChange={(event) => {
              setFile(event.target.files?.[0] ?? null);
              setPreview(null);
              setMessage(null);
            }}
          />
          <small>
            {file
              ? `${file.name} · ${number.format(file.size / 1024)} KB`
              : "ไฟล์ Daily ของ Thai-Aust"}
          </small>
        </label>
        <button
          className="primary-action hp-mh-preview-action"
          type="button"
          disabled={!file || busy !== null}
          onClick={() => void inspect()}
        >
          {busy === "preview" ? "กำลังตรวจสอบ…" : "ตรวจสอบไฟล์"}
        </button>
      </div>
      {progress && (
        <div className="import-transfer" role="status">
          <div>
            <span>
              {progress.phase === "uploading"
                ? "กำลังส่งไฟล์เข้า Server"
                : "กำลังอ่านและตรวจข้อมูล"}
            </span>
            <strong>
              {progress.phase === "uploading"
                ? `${progress.percent}%`
                : "โปรดรอสักครู่"}
            </strong>
          </div>
          <div
            className="import-transfer-track"
            data-indeterminate={progress.phase !== "uploading" || undefined}
          >
            <span
              style={{
                width:
                  progress.phase === "uploading"
                    ? `${progress.percent}%`
                    : "38%",
              }}
            />
          </div>
        </div>
      )}
      {message && (
        <div className="import-message" role="status">
          {message}
        </div>
      )}
      {preview && (
        <div
          className="preview-stage hp-mh-preview"
          data-blocked={!preview.canImport || undefined}
        >
          <header>
            <div>
              <span className="stage-number">2</span>
              <div>
                <span className="eyebrow">ผลการตรวจสอบ</span>
                <h3>Thai-Aust · {formatDisplayDate(preview.dataDate)}</h3>
              </div>
            </div>
            <span
              className={`preview-state ${preview.canImport ? "ready" : "blocked"}`}
            >
              {preview.canImport ? (
                <CheckCircle2 size={16} />
              ) : (
                <AlertTriangle size={16} />
              )}
              {preview.canImport
                ? preview.operation === "replace"
                  ? "พร้อมแทนที่ข้อมูลเดิม"
                  : "พร้อมนำเข้า"
                : "ไม่สามารถนำเข้า"}
            </span>
          </header>
          <div className="hp-mh-summary-grid">
            <article>
              <strong>Thai-Aust (TA)</strong>
              <dl>
                <div>
                  <dt>รายการ</dt>
                  <dd>{number.format(preview.summary.rowCount)}</dd>
                </div>
                <div>
                  <dt>SKU</dt>
                  <dd>{number.format(preview.summary.skuCount)}</dd>
                </div>
                <div>
                  <dt>Branch</dt>
                  <dd>{number.format(preview.summary.branchCount)}</dd>
                </div>
                <div>
                  <dt>Amount Ex.VAT</dt>
                  <dd>{number.format(preview.summary.amount)}</dd>
                </div>
                <div>
                  <dt>Sales Qty</dt>
                  <dd>{number.format(preview.summary.salesQty)}</dd>
                </div>
                <div>
                  <dt>Stock</dt>
                  <dd>{number.format(preview.summary.stockOnHand)}</dd>
                </div>
              </dl>
            </article>
          </div>
          {preview.warnings.length > 0 && (
            <div className="preview-warning">
              <AlertTriangle size={16} />
              {preview.warnings.join(" · ")}
            </div>
          )}
          {preview.operation === "replace" && (
            <div className="preview-warning">
              <AlertTriangle size={16} />
              วันนี้มีข้อมูลใน Batch {preview.replacementBatchId} แล้ว
              ต้องยืนยันเพื่อแทนที่แบบ Atomic
            </div>
          )}
          {preview.duplicateReason && (
            <div className="preview-warning blocked">
              <AlertTriangle size={16} />
              {preview.duplicateReason}
            </div>
          )}
          <footer>
            <small>
              Report/Dashboard จะแสดงเฉพาะ Item และ Branch ที่ Confirmed +
              Active
            </small>
            <button
              className="primary-action"
              type="button"
              disabled={!preview.canImport || busy !== null}
              onClick={() => void confirm()}
            >
              {busy === "confirm"
                ? "กำลังบันทึก…"
                : preview.operation === "replace"
                  ? "ยืนยันแทนที่ข้อมูล Thai-Aust"
                  : "ยืนยันนำเข้า Thai-Aust"}
            </button>
          </footer>
        </div>
      )}
    </section>
  );
}
