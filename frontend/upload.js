const API_URL = "/api";

const FIELD_LABELS = {
    type_of_doc: "Document type",
    id: "Invoice number",
    date: "Date",
    hour: "Time",
};
const PARTY_LABELS = { name: "Name", id: "ID / company no.", phone: "Phone", address: "Address" };
const TOTAL_LABELS = [
    ["price_before_rounding", "Before rounding"],
    ["rounding", "Rounding"],
    ["discount", "Discount"],
    ["price_before_VAT", "Before VAT"],
    ["vat_amount", "VAT"],
    ["total_price", "Total"],
];

function el(tag, attrs = {}, children = []) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
        if (key === "text") node.textContent = value;
        else node.setAttribute(key, value);
    }
    for (const child of children) node.append(child);
    return node;
}

function value_node(value) {
    if (value === null || value === undefined || value === "") {
        return el("span", { class: "empty", text: "—" });
    }
    return el("span", { dir: "auto", text: String(value) });
}

function money(value) {
    if (value === null || value === undefined) return null;
    const number = Number(value);
    if (Number.isNaN(number)) return value;
    return number.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function field(label, value) {
    return el("div", { class: "field" }, [
        el("div", { class: "label", text: label }),
        el("div", { class: "value" }, [value_node(value)]),
    ]);
}

function show_status(kind, title, items = []) {
    const status = document.getElementById("status");
    status.className = `status ${kind}`;
    status.replaceChildren();
    if (kind === "loading") status.append(el("span", { class: "spinner" }));
    status.append(el("strong", { text: title }));
    if (items.length) status.append(el("ul", {}, items.map((item) => el("li", { text: item }))));
    status.hidden = false;
}

function render_party(title, party) {
    const card = el("div", {}, [el("h3", { text: title })]);
    const fields = el("div", { class: "fields" });
    for (const [key, label] of Object.entries(PARTY_LABELS)) {
        fields.append(field(label, party ? party[key] : null));
    }
    card.append(fields);
    return card;
}

function render_products(products) {
    const head = el("tr", {}, [
        el("th", { text: "Item no." }),
        el("th", { text: "Description" }),
        el("th", { class: "num", text: "Qty" }),
        el("th", { class: "num", text: "Unit price" }),
        el("th", { class: "num", text: "Discount" }),
        el("th", { class: "num", text: "Line total" }),
    ]);
    const rows = (products || []).map((product) => el("tr", {}, [
        el("td", {}, [value_node(product.id)]),
        el("td", {}, [value_node(product.name)]),
        el("td", { class: "num" }, [value_node(product.quantity)]),
        el("td", { class: "num" }, [value_node(money(product.price_for_unit))]),
        el("td", { class: "num" }, [value_node(money(product.discount))]),
        el("td", { class: "num" }, [value_node(money(product.product_total_price))]),
    ]));
    if (!rows.length) rows.push(el("tr", {}, [el("td", { colspan: "6", class: "empty", text: "No line items found" })]));
    return el("div", { class: "table_wrap" }, [el("table", {}, [el("thead", {}, [head]), el("tbody", {}, rows)])]);
}

function render_totals(invoice) {
    const rows = TOTAL_LABELS.map(([key, label]) => el("tr", { class: key === "total_price" ? "grand" : "" }, [
        el("td", { text: label }),
        el("td", { class: "num" }, [value_node(money(invoice[key]))]),
    ]));
    return el("table", { class: "totals" }, [el("tbody", {}, rows)]);
}

function render_invoice(invoice) {
    const view = document.getElementById("invoice_view");
    view.replaceChildren();
    if (!invoice) {
        view.append(el("p", { class: "empty", text: "No invoice could be extracted." }));
        return;
    }
    const header = el("div", { class: "fields" });
    for (const [key, label] of Object.entries(FIELD_LABELS)) header.append(field(label, invoice[key]));
    view.append(
        header,
        el("div", { class: "parties" }, [
            render_party("Supplier", invoice.supplier),
            render_party("Customer", invoice.customer),
        ]),
        el("h3", { text: "Line items" }),
        render_products(invoice.products),
        el("h3", { text: "Totals" }),
        render_totals(invoice),
    );
}

function show_response(result, original_url) {
    document.getElementById("original_image").src = original_url;
    document.getElementById("preprocessed_image").src = result.preprocessed_image || "";
    document.getElementById("ocr_text").textContent = result.raw_text || "";
    render_invoice(result.invoice);
    const { preprocessed_image, ...json } = result;
    document.getElementById("json_response").textContent = JSON.stringify(json, null, 2);
    document.getElementById("results").hidden = false;
}

function set_busy(busy) {
    for (const button of document.querySelectorAll("button")) button.disabled = busy;
    document.getElementById("image_upload").disabled = busy;
    if (!busy) document.getElementById("send").disabled = !document.getElementById("image_upload").files.length;
}

async function sendData(file) {
    const formData = new FormData();
    formData.append("file", file);
    const original_url = URL.createObjectURL(file);
    set_busy(true);
    document.getElementById("results").hidden = true;
    show_status("loading", "Running OCR and extraction… this usually takes 10–30 seconds.");
    try {
        const response = await fetch(API_URL, { method: "POST", body: formData });
        const body = await response.json().catch(() => ({}));
        if (response.ok) {
            const notes = [...body.warnings.map((w) => `Warning: ${w}`),
                           ...body.fixed_errors.map((f) => `Fixed on retry: ${f}`)];
            show_status(body.warnings.length ? "warn" : "ok",
                `Extracted successfully (attempts: ${body.attempts})`, notes);
            show_response(body, original_url);
        } else if (response.status === 422 && body.detail && typeof body.detail === "object") {
            const detail = body.detail;
            show_status("error", "Extraction finished, but validation failed:",
                [...detail.errors, ...detail.warnings.map((w) => `Warning: ${w}`)]);
            show_response(detail, original_url);
        } else if (response.status === 400) {
            show_status("error", "That file could not be read as an image.");
        } else if (response.status === 502) {
            show_status("error", "The language model service failed. Check the API key and try again.", [String(body.detail || "")]);
        } else {
            show_status("error", `Unexpected server error (${response.status}).`, [JSON.stringify(body.detail || body)]);
        }
    } catch (e) {
        console.error(e);
        show_status("error", "Could not reach the server. Is the API running?");
    } finally {
        set_busy(false);
    }
}

async function load_samples() {
    const container = document.getElementById("samples");
    try {
        const response = await fetch(`${API_URL}/samples`);
        const samples = await response.json();
        for (const sample of samples) {
            const button = el("button", { class: "sample", type: "button", title: sample.name }, [
                el("img", { src: sample.url, alt: sample.description, loading: "lazy" }),
                el("span", { text: sample.description }),
            ]);
            button.addEventListener("click", async () => {
                const image = await fetch(sample.url);
                const blob = await image.blob();
                sendData(new File([blob], sample.name, { type: blob.type }));
            });
            container.append(button);
        }
    } catch (e) {
        console.error(e);
    }
}

const upload = document.getElementById("image_upload");
const send = document.querySelector("#send");
upload.addEventListener("change", () => { send.disabled = !upload.files.length; });
send.addEventListener("click", () => {
    if (upload.files[0]) sendData(upload.files[0]);
});
load_samples();
