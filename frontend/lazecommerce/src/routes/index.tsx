import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState, useId } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { PipelineShell } from "@/components/pipeline/PipelineShell";
import { BootScreen } from "@/components/pipeline/BootScreen";
import { ExtractStep } from "@/components/pipeline/ExtractStep";
import { GenerateStep } from "@/components/pipeline/GenerateStep";
import { PublishStep } from "@/components/pipeline/PublishStep";
import type { PipelineStep } from "@/components/pipeline/types";
import type { ProductData } from "@/lib/mock-api";

export const Route = createFileRoute("/")(({
  head: () => ({
    meta: [
      { title: "LazECommerce — AI Web Scraper to Zoho Publisher" },
      {
        name: "description",
        content:
          "Guided 4-step pipeline that scrapes product pages, generates AI listings, and publishes to Zoho with human approval at every step.",
      },
    ],
  }),
  component: PipelinePage,
}));

function PipelinePage() {
  const [step, setStep] = useState<PipelineStep>("boot");
  const [url, setUrl] = useState("");
  const [vendor, setVendor] = useState("Quartzcomponents");
  const [rawText, setRawText] = useState("");
  const [productId, setProductId] = useState<string | null>(null);
  const [data, setData] = useState<ProductData | null>(null);
  const [categoryId, setCategoryId] = useState<string | null>(null);
  // Image pipeline state
  const [scrapedImages, setScrapedImages] = useState<string[]>([]);
  const [approvedImages, setApprovedImages] = useState<string[]>([]);

  const uid = useId();
  const pipelineId = useMemo(
    () => "PX-" + uid.replace(/:/g, "").slice(0, 5),
    [uid]
  );

  function reset() {
    setUrl("");
    setVendor("Quartzcomponents");
    setRawText("");
    setProductId(null);
    setData(null);
    setCategoryId(null);
    setScrapedImages([]);
    setApprovedImages([]);
    setStep("extract");
  }

  return (
    <PipelineShell step={step} pipelineId={pipelineId}>
      <AnimatePresence mode="wait">
        <motion.div
          key={step}
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -12 }}
          transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
        >
          {step === "boot" && <BootScreen onComplete={() => setStep("extract")} />}
          {step === "extract" && (
            <ExtractStep
              initial={{ url, vendor, rawText }}
              onApprove={(v) => {
                setUrl(v.url);
                setVendor(v.vendor);
                setRawText(v.raw_text);
                setScrapedImages(v.images ?? []);
                setStep("generate");
              }}
            />
          )}
          {step === "generate" && (
            <GenerateStep
              source={{ vendor, source_url: url, raw_text: rawText }}
              initialData={data}
              initialProductId={productId}
              scrapedImages={scrapedImages}
              onProductId={setProductId}
              onApprove={(d, pid, catId, approvedImgs) => {
                setData(d);
                setProductId(pid);
                setCategoryId(catId);
                setApprovedImages(approvedImgs);
                setStep("publish");
              }}
            />
          )}
          {(step === "publish" || step === "done") && productId && data && (
            <PublishStep
              productId={productId}
              productTitle={data.product_title}
              categoryId={categoryId}
              approvedImages={approvedImages}
              onReset={reset}
            />
          )}
        </motion.div>
      </AnimatePresence>
    </PipelineShell>
  );
}
