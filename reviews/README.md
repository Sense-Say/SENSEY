I have converted the "Flexion Angle" calculation into a clean Microsoft Word document.

I corrected the syntax from the raw code (like `SQRT()`) into proper mathematical notation ($\sqrt{...}$) so it looks professional.

### **Download Word File**
**[Download Flexion_Angle_Calculation.docx](sandbox:/mnt/data/Flexion_Angle_Calculation.docx)**

***

### **Copy & Paste Text**
Here is the text formatted for you to copy directly:

**Flexion Angle Formula**
$\theta = \cos^{-1} \left( \frac{\vec{SSSB} \cdot \vec{LSRE}}{|\vec{SSSB}| \times |\vec{LSRE}|} \right)$

**Substitution**
$= \cos^{-1} \left( \frac{(0.0174)(-0.2424) + (-0.5707)(0.0256) + (-0.0350)(0)}{\sqrt{(0.0174)^2 + (-0.5707)^2 + (-0.0350)^2} \times \sqrt{(-0.2424)^2 + (0.0256)^2 + (0)^2}} \right)$

**Result**
**Flexion Angle = 97.55282579°**

**Error Calculation**
**Flexion Angle Error = 0.006974210597**

***

**Python Code Used:**
```python
from docx import Document
from docx.shared import Pt

doc = Document()
doc.add_heading('Flexion Angle Calculation', 0)

# Formula
p_form = doc.add_paragraph()
run_form = p_form.add_run("Flexion Angle = Cos⁻¹ ( (SSSB • LSRE) / (|SSSB| * |LSRE|) )")
run_form.bold = True
run_form.font.size = Pt(11)

# Expansion
doc.add_paragraph("Numerator (Dot Product):")
doc.add_paragraph("= (SSSB.x * LSRE.x) + (SSSB.y * LSRE.y) + (SSSB.z * LSRE.z)")
doc.add_paragraph("Denominator (Magnitudes):")
doc.add_paragraph("= √((SSSB.x)² + (SSSB.y)² + (SSSB.z)²) * √((LSRE.x)² + (LSRE.y)² + (LSRE.z)²)")

doc.add_paragraph("") # Spacer

# Substitution
p_sub = doc.add_paragraph()
run_sub = p_sub.add_run("Substitution:")
run_sub.bold = True

doc.add_paragraph("= Cos⁻¹ [ ( (0.0174 * -0.2424) + (-0.5707 * 0.0256) + (-0.0350 * 0) ) / ")
doc.add_paragraph("  ( √(0.0174² + -0.5707² + -0.0350²) * √(-0.2424² + 0.0256² + 0²) ) ]")

doc.add_paragraph("") # Spacer

# Final Result
p_res = doc.add_paragraph()
run_res = p_res.add_run("Flexion Angle = 97.55282579°")
run_res.bold = True
run_res.font.size = Pt(12)

# Error
p_err = doc.add_paragraph()
run_err = p_err.add_run("Flexion Angle Error = 0.006974210597")
run_err.bold = True

doc.save("Flexion_Angle_Calculation.docx")
```