import streamlit as st
import fitz  # PyMuPDF
from streamlit_drawable_canvas import st_canvas   # clouddaki uygun versiyon 0.8.0
from PIL import Image, ImageDraw, ImageFont
import io
import os
import base64
import time


st.set_page_config(
    page_title="InvoiceRedactor v0.2.0",
    page_icon="🔐",
    layout="wide"
)
st.title("PDF Bilgi Gizleyici")
st.markdown("---")

st.info("Aşağıdan düzenlemek istediğiniz pdf'i yükleyin. Sol taraftaki pdf üzerinden düzenleme yaparak sağ taraftaki kısmdan önizleyebilirsiniz gizlenmiş kısımları. Her seferinde tek bir fatura belgesi yükleyebilirsiniz.")


st.markdown("""
    <style>
    .stButton > button {
        display: block;
        margin: 0 auto;
        width: 100%;
    }
    </style>
""", unsafe_allow_html=True)


KVKK_NOTU = "KVKK nedeniyle silinmiştir"

def get_font(size=12):
    """Font yükleme """
    font_candidates = [
        "fonts/arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
    return ImageFont.load_default()

def get_pdf_font_name():
    """PyMuPDF için kullanılabilir font dönüştürür."""
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return None  

@st.cache_data
def convert_pdf_to_image(pdf_bytes):
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
    return Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB")

def pil_to_base64(img: Image.Image) -> str:
    """PIL Image'ı base64 string'e çevirir — canvas için must"""
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


# --- Session state başlangıç değerleri ---
if "processed_pdf" not in st.session_state:
    st.session_state.processed_pdf = None
if "file_uploaded" not in st.session_state:
    st.session_state.file_uploaded = False
if "clearing" not in st.session_state:
    st.session_state.clearing = False
if "countdown" not in st.session_state:
    st.session_state.countdown = 3
if "clearing_reason" not in st.session_state:
    st.session_state.clearing_reason = "download"  # "download" veya "cancel"


# --- Temizleme sekansı (indirme veya iptal sonrası) ---
if st.session_state.clearing:
    remaining = st.session_state.countdown

    if st.session_state.clearing_reason == "download":
        st.success("✅ İşlem tamamlandı — dosya indirildi.")
        detail_msg = "Yüklenen PDF ve işlenmiş dosya bellekten silindi."
    else:
        st.warning("🚫 İşlem iptal edildi.")
        detail_msg = "İşlem iptal edildi. Yüklenen PDF bellekten silindi."

    st.markdown(f"""
        <div style="
            background-color: #f0fff4;
            border: 1px solid #68d391;
            border-radius: 8px;
            padding: 16px 20px;
            margin: 12px 0;
        ">
            <p style="margin:0; font-size:15px;">
                🔒 <b>Oturum verileri temizlendi.</b> {detail_msg}
            </p>
            <p style="margin:8px 0 0 0; color:#555; font-size:13px;">
                ⏱️ <b>{remaining}</b> saniye içinde başa dönülüyor...
            </p>
        </div>
    """, unsafe_allow_html=True)

    st.progress((3 - remaining) / 3)

    time.sleep(1)
    st.session_state.countdown -= 1

    if st.session_state.countdown <= 0:
        st.session_state.clear()
        st.rerun()
    else:
        st.rerun()

    st.stop()


# --- Ana akış ---
if not st.session_state.file_uploaded:
    uploaded_file = st.file_uploader("PDF Yükleyin", type="pdf", key="main_uploader")
    if uploaded_file:
        pdf_bytes = uploaded_file.read()
        # Sayfa sayısı kontrolü
        doc_check = fitz.open(stream=pdf_bytes, filetype="pdf")
        if len(doc_check) > 1:
            st.error(f"❌ Yalnızca tek sayfalı PDF'ler desteklenmektedir. Yüklediğiniz dosya {len(doc_check)} sayfa içeriyor.")
        else:
            st.session_state.pdf_bytes = pdf_bytes
            st.session_state.file_name = uploaded_file.name
            st.session_state.file_uploaded = True
            st.rerun()
else:
   
    st.markdown("""
        <style>
        div[data-testid='stFileUploader'] { display: none !important; }
        div[data-testid='stFileUploaderDropzone'] { display: none !important; }
        </style>
    """, unsafe_allow_html=True)

    # Prep alanı
    img_pil = convert_pdf_to_image(st.session_state.pdf_bytes)
    display_width = 700
    ratio = display_width / img_pil.width
    display_height = int(img_pil.height * ratio)
    display_img = img_pil.resize((display_width, display_height), Image.Resampling.LANCZOS)

    # editleme alanı
    left_col, right_col = st.columns([1, 1])

    with left_col:
        st.subheader("✏️ Karartılacak Alanları Çizin")

        canvas_result = st_canvas(
            fill_color="rgba(0, 150, 255, 0.2)",
            stroke_width=1,
            stroke_color="#0096FF",
            background_image=display_img,   
            update_streamlit=True,
            drawing_mode="rect",
            width=display_width,
            height=display_height,
            key="canvas_work",
        )

    with right_col:
        st.subheader("🔍 Önizleme")
        preview_img = display_img.copy()
        draw = ImageDraw.Draw(preview_img)

        if canvas_result.json_data and "objects" in canvas_result.json_data:
            for obj in canvas_result.json_data["objects"]:
                l = obj["left"]
                t = obj["top"]
                w = obj["width"]
                h = obj["height"]
                draw.rectangle([l, t, l + w, t + h], fill="white", outline="#CCCCCC")
                dynamic_size = max(6, min(14, int(h * 0.6)))
                p_font = get_font(dynamic_size)
                if h > 5:
                    draw.text((l + w / 2, t + h / 2), KVKK_NOTU,
                              fill="red", font=p_font, anchor="mm")

        st.image(preview_img, width=display_width)

   
    st.markdown("---")
    btn_col1, btn_col2 = st.columns([1, 1])

    with btn_col1:
        if st.button("❌ İşlemi İptal Et", use_container_width=True):
            for key in ["pdf_bytes", "processed_pdf", "file_uploaded", "file_name"]:
                st.session_state.pop(key, None)
            st.session_state.clearing = True
            st.session_state.clearing_reason = "cancel"
            st.session_state.countdown = 3
            st.rerun()

    with btn_col2:
        if st.button("🚀 PDF'i Hazırla", type="primary", use_container_width=True):
            if canvas_result.json_data and len(canvas_result.json_data["objects"]) > 0:
                with st.spinner("PDF Oluşturuluyor..."):
                    doc = fitz.open(stream=st.session_state.pdf_bytes, filetype="pdf")
                    page = doc[0]
                    pdf_scale_x = page.rect.width / display_width
                    pdf_scale_y = page.rect.height / display_height
                    custom_font_path = get_pdf_font_name()

                    for obj in canvas_result.json_data["objects"]:
                        x0 = obj["left"] * pdf_scale_x
                        y0 = obj["top"] * pdf_scale_y
                        w_p = obj["width"] * pdf_scale_x
                        h_p = obj["height"] * pdf_scale_y
                        rect = fitz.Rect(x0, y0, x0 + w_p, y0 + h_p)
                        pdf_fsize = max(5, min(10, int(h_p * 0.6)))

                        for p in doc:
                            p.add_redact_annot(rect, fill=(1, 1, 1))
                            p.apply_redactions()
                            try:
                                if custom_font_path:
                                    p.insert_textbox(
                                        rect, KVKK_NOTU,
                                        fontsize=pdf_fsize,
                                        fontname="f0",
                                        fontfile=custom_font_path,
                                        color=(1, 0, 0),
                                        align=1
                                    )
                                else:
                                    p.insert_textbox(
                                        rect, "KVKK gizlendi",
                                        fontsize=pdf_fsize,
                                        color=(1, 0, 0),
                                        align=1
                                    )
                            except Exception as e:
                                st.warning(f"Metin eklenemedi: {e}")

                    st.session_state.processed_pdf = doc.tobytes()
            else:
                st.error("Lütfen en az bir alan seçin.")

    if st.session_state.processed_pdf:
        st.success("✅ PDF Hazır!")
        if st.download_button(
            label="📥 Düzenlenmiş PDF'i İndir",
            data=st.session_state.processed_pdf,
            file_name=f"redacted_{st.session_state.file_name}",
            mime="application/pdf",
            use_container_width=True
        ):
            # Hassas veriyi hemen temizle, sonra sekansı başlat
            for key in ["pdf_bytes", "processed_pdf", "file_uploaded", "file_name"]:
                st.session_state.pop(key, None)
            st.session_state.clearing = True
            st.session_state.clearing_reason = "download"
            st.session_state.countdown = 3
            st.rerun()
