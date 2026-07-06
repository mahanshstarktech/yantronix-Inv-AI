// Real API connecting to FastAPI backend
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

// ── Types ─────────────────────────────────────────────────────────────────────

export type ExtractResponse = {
  url: string;
  vendor: string;
  raw_text: string;
};

export type GenerateResponse = {
  success: boolean;
  message: string;
  product_id: string;
  vendor: string;
  text_length: number;
};

export type ProductData = {
  product_title: string;
  seo_title: string;
  meta_description: string;
  sku: string;
  brand: string;
  hsn_code: string;
  base_price: number;
  final_selling_price: number;
  tags: string[];
  seo_keywords: string[];
  short_description_html: string;
  long_description_html: string;
};

export type StatusResponse =
  | { status: "PROCESSING"; data: null; error: null }
  | { status: "COMPLETE"; data: ProductData; error: null }
  | { status: "ERROR"; data: null; error: string };

/** A single Zoho category node — may have nested children. */
export type CategoryNode = {
  category_id: string;
  name: string;
  parent_category_id: string;
  depth: number;
  visibility: boolean;
  children: CategoryNode[];
};

export type CategoryTreeResponse = {
  tree: CategoryNode[];
  flat: CategoryNode[];
  total: number;
  cached: boolean;
};

export type CategorySuggestResponse = {
  category_id: string | null;
  category_name: string | null;
  confidence: number;
  reasoning: string;
};

export type ZohoBrand = {
  brand_id: string;
  name: string;
};

// ── API functions ─────────────────────────────────────────────────────────────

export async function extract(url: string): Promise<ExtractResponse> {
  const res = await fetch(`${API_BASE_URL}/extract`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url }),
  });
  if (!res.ok) {
    throw new Error(`Failed to extract data: ${res.statusText}`);
  }
  const data = await res.json();
  return {
    url: data.source_url || url,
    vendor: data.vendor,
    raw_text: data.raw_text,
  };
}

export async function generate(input: {
  vendor: string;
  source_url: string;
  raw_text: string;
}): Promise<GenerateResponse> {
  const res = await fetch(`${API_BASE_URL}/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(input),
  });
  if (!res.ok) {
    throw new Error(`Failed to generate AI listing: ${res.statusText}`);
  }
  return res.json();
}

export async function getStatus(product_id: string): Promise<StatusResponse> {
  const res = await fetch(`${API_BASE_URL}/status/${product_id}`);
  if (!res.ok) {
    throw new Error(`Failed to get status: ${res.statusText}`);
  }
  const backendData = await res.json();

  if (backendData.status === "complete") {
    const aiData = backendData.data;
    return {
      status: "COMPLETE",
      data: {
        product_title: aiData.product_title || "",
        seo_title: aiData.seo_title || "",
        meta_description: aiData.meta_description || "",
        sku: aiData.sku || "",
        brand: aiData.brand || "",
        hsn_code: aiData.hsn_code || "",
        base_price:
          aiData.selling_price?.vendor_base_price ??
          aiData.selling_price?.quartz_base_price ??
          0,
        final_selling_price: aiData.selling_price?.final_selling_price ?? 0,
        tags: aiData.tags || [],
        seo_keywords: aiData.seo_keywords || [],
        short_description_html: aiData.short_description_html || "",
        long_description_html: aiData.long_description_html || "",
      },
      error: null,
    };
  } else if (backendData.status === "failed" || backendData.status === "error") {
    return {
      status: "ERROR",
      data: null,
      error: backendData.error || "Generation failed",
    };
  }

  return { status: "PROCESSING", data: null, error: null };
}

/** Fetch the full Zoho category tree. Pass refresh=true to bust the server cache. */
export async function getCategories(refresh = false): Promise<CategoryTreeResponse> {
  const url = `${API_BASE_URL}/categories${refresh ? "?refresh=true" : ""}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch categories: ${res.statusText}`);
  }
  return res.json();
}

/** Ask Gemini to suggest the best Zoho category for a product. */
export async function suggestCategory(
  product: Pick<ProductData, "product_title" | "tags" | "seo_keywords" | "short_description_html">,
  categories: Array<{ category_id: string; name: string }>
): Promise<CategorySuggestResponse> {
  const res = await fetch(`${API_BASE_URL}/categories/suggest`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      product_title: product.product_title,
      tags: product.tags,
      seo_keywords: product.seo_keywords,
      short_description_html: product.short_description_html,
      categories,
    }),
  });
  if (!res.ok) {
    throw new Error(`Failed to suggest category: ${res.statusText}`);
  }
  return res.json();
}

/** Publish the product to Zoho, optionally with a specific category_id. */
export async function publish(
  product_id: string,
  category_id?: string | null
): Promise<{
  success: boolean;
  product_id?: string;
  zoho_id?: string;
  category_id?: string | null;
  message?: string;
  result?: any;
}> {
  const res = await fetch(`${API_BASE_URL}/publish/${product_id}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ category_id: category_id ?? null }),
  });
  if (!res.ok) {
    let errorMessage = res.statusText;
    try {
      const errorData = await res.json();
      errorMessage = errorData.detail || errorMessage;
    } catch (e) {
      // Ignore json parse error
    }
    throw new Error(`Failed to publish: ${errorMessage}`);
  }
  const data = await res.json();

  // Try to extract a Zoho product ID from the response
  const zohoId =
    data.result?.item?.item_id ||
    data.result?.product?.product_id ||
    (data.result?.test_mode ? `TEST-${product_id.substring(0, 6)}` : null);

  return { ...data, zoho_id: zohoId };
}

/** Fetch all Zoho Commerce brands. */
export async function getBrands(refresh = false): Promise<{ brands: ZohoBrand[]; total: number }> {
  const url = `${API_BASE_URL}/brands${refresh ? "?refresh=true" : ""}`;
  const res = await fetch(url);
  if (!res.ok) {
    throw new Error(`Failed to fetch brands: ${res.statusText}`);
  }
  return res.json();
}
