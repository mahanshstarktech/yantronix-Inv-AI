import { createFileRoute } from "@tanstack/react-router";
import { useMemo, useState, useEffect } from "react";
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
  
  // NEW: Store marketplace selections at the top level
  const [sendToAmazon, setSendToAmazon] = useState(false);
  const [sendToFlipkart, setSendToFlipkart] = useState(false);

  const [pipelineId, setPipelineId] = useState("PX-00000");

  useEffect(() => {
    setPipelineId("PX-" + Math.floor(10000 + Math.random() * 89999));
  }, []);

  function reset() {
    setUrl("");
    setVendor("Quartzcomponents");
    setRawText("");
    setProductId(null);
    setData(null);
    setCategoryId(null);
    setSendToAmazon(false); // NEW: Reset selections
    setSendToFlipkart(false); // NEW: Reset selections
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
                setStep("generate");
              }}
            />
          )}
          {step === "generate" && (
            <GenerateStep
              source={{ vendor, source_url: url, raw_text: rawText }}
              initialData={data}
              initialProductId={productId}
              onProductId={setProductId}
              // UPDATE: Accept amazon/flipkart selections here
              onApprove={(d, pid, catId, amazon, flipkart) => {
                setData(d);
                setProductId(pid);
                setCategoryId(catId);
                setSendToAmazon(amazon);
                setSendToFlipkart(flipkart);
                setStep("publish");
              }}
            />
          )}
          {(step === "publish" || step === "done") && productId && data && (
            <PublishStep
              productId={productId}
              productTitle={data.product_title}
              categoryId={categoryId}
              // UPDATE: Pass selections down to the final publishing screen
              sendToAmazon={sendToAmazon}
              sendToFlipkart={sendToFlipkart}
              onReset={reset}
            />
          )}
        </motion.div>
      </AnimatePresence>
    </PipelineShell>
  );
}