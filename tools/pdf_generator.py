import json
from tools.registry import registry
from fpdf import FPDF

def generate_pdf(client_name, amount, output_path="/opt/data/quote.pdf"):
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Header
        pdf.set_font("helvetica", "B", 18)
        pdf.cell(w=0, h=10, txt="Loops Technologies - Official Quote", ln=1, align="C")
        pdf.ln(20)
        
        # Body
        pdf.set_font("helvetica", "", 12)
        pdf.cell(w=0, h=10, txt=f"Prepared For: {client_name}", ln=1)
        pdf.cell(w=0, h=10, txt="Service: AI Automation & Integration", ln=1)
        pdf.ln(10)
        
        # Pricing
        pdf.set_font("helvetica", "B", 14)
        pdf.cell(w=0, h=10, txt=f"Total Investment: {amount} SAR", ln=1)
        
        pdf.output(output_path)
        
        return json.dumps({"success": True, "file_path": output_path})
    except Exception as e:
        return json.dumps({"error": str(e)})

# The Schema tells Hermes how to use the tool
PDF_SCHEMA = {
    "name": "generate_pdf_quote",
    "description": "Generate a professional PDF quote for a client. Use this whenever the user asks to create a quote, proposal, or price estimate.",
    "parameters": {
        "type": "object",
        "properties": {
             "client_name": {"type": "string", "description": "The name of the client or company"},
             "amount": {"type": "number", "description": "The total price in SAR"},
             "file_name": {"type": "string", "description": "Optional specific file name, e.g., quote_ahmed.pdf"}
        },
        "required": ["client_name", "amount"]
    }
}

registry.register(
    name="generate_pdf_quote",
    toolset="custom",
    schema=PDF_SCHEMA,
    handler=lambda args, **kw: generate_pdf(
        args.get("client_name", "Unknown"), 
        args.get("amount", 0), 
        args.get("file_name") if args.get("file_name") and str(args.get("file_name")).startswith("/opt/data/") else f"/opt/data/{args.get('file_name', 'quote.pdf')}"
    )
)