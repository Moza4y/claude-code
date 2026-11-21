const fs = require('fs');
const d = require('docx');
const { Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, WidthType, ShadingType, AlignmentType,
  HeadingLevel, LevelFormat, BorderStyle, Footer, PageNumber, PageBreak } = d;

const FONT = "Arial";
const BLUE = "1F3864", ACC = "0078D7";
let figN = 0;

// ---------- inline markup: **bold**  `code`
function runs(text, o = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  const base = { font: FONT, rightToLeft: true, size: o.size || 24, color: o.color, bold: o.bold, italics: o.italics };
  const push = (t, extra) => { if (t) out.push(new TextRun({ ...base, text: t, ...extra })); };
  while ((m = re.exec(text))) {
    push(text.slice(last, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) push(tok.slice(2, -2), { bold: true });
    else push(tok.slice(1, -1), { font: "Consolas", rightToLeft: false, size: (o.size || 24) - 2, shading: { type: ShadingType.CLEAR, fill: "F0F0F0", color: "auto" } });
    last = m.index + tok.length;
  }
  push(text.slice(last));
  return out;
}
const P = (t, o = {}) => new Paragraph({ bidirectional: true, spacing: { after: o.after ?? 120, line: 320 }, keepNext: o.keepNext, alignment: o.align, children: runs(t, o) });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, bidirectional: true, keepNext: true, spacing: { before: 360, after: 160 }, children: [new TextRun({ text: t, font: FONT, rightToLeft: true, bold: true, size: 32, color: BLUE })] });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, bidirectional: true, keepNext: true, spacing: { before: 240, after: 120 }, children: [new TextRun({ text: t, font: FONT, rightToLeft: true, bold: true, size: 27, color: ACC })] });
const B = (t) => new Paragraph({ bidirectional: true, numbering: { reference: "bul", level: 0 }, spacing: { after: 80, line: 320 }, children: runs(t) });
let stepRefs = 0; const stepCfg = [];
function steps(items) {
  const ref = "st" + (++stepRefs);
  stepCfg.push({ reference: ref, levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.START, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] });
  return items.map(t => new Paragraph({ bidirectional: true, numbering: { reference: ref, level: 0 }, spacing: { after: 90, line: 320 }, children: runs(t) }));
}
const NOTE = { tip: ["EAF3FF", "0078D7", "ملحوظة: "], warn: ["FFF4E5", "E08A00", "تنبيه: "], bad: ["FDECEC", "C62828", "مهم: "] };
const note = (kind, t) => new Paragraph({ bidirectional: true, spacing: { before: 80, after: 160, line: 320 },
  shading: { type: ShadingType.CLEAR, fill: NOTE[kind][0], color: "auto" },
  border: { right: { style: BorderStyle.SINGLE, size: 24, color: NOTE[kind][1], space: 8 } },
  indent: { right: 120, left: 120 },
  children: [new TextRun({ text: NOTE[kind][2], bold: true, font: FONT, rightToLeft: true, size: 24, color: NOTE[kind][1] }), ...runs(t)] });

function png(file) { const b = fs.readFileSync(file); return { data: b, w: b.readUInt32BE(16), h: b.readUInt32BE(20) }; }
function fig(name, caption, maxW = 620) {
  const im = png(`img/${name}.png`); const w = Math.min(maxW, im.w), h = Math.round(im.h * w / im.w);
  figN++;
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, keepNext: true, spacing: { before: 120, after: 60 }, children: [new ImageRun({ type: "png", data: im.data, transformation: { width: w, height: h }, altText: { title: caption, description: caption, name } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, bidirectional: true, spacing: { after: 200 }, children: runs(`شكل ${figN}: ${caption}`, { size: 20, color: "595959", italics: true }) }),
  ];
}
const bd = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: bd, bottom: bd, left: bd, right: bd };
function table(headers, rows, widths) {
  const mk = (t, w, head) => new TableCell({ width: { size: w, type: WidthType.DXA }, borders, margins: { top: 70, bottom: 70, left: 110, right: 110 },
    shading: head ? { type: ShadingType.CLEAR, fill: "D5E8F0", color: "auto" } : undefined,
    children: [new Paragraph({ bidirectional: true, spacing: { after: 0, line: 300 }, children: runs(t, { size: 21, bold: head }) })] });
  return new Table({ visuallyRightToLeft: true, width: { size: widths.reduce((a, b) => a + b, 0), type: WidthType.DXA }, columnWidths: widths,
    rows: [new TableRow({ tableHeader: true, children: headers.map((h, i) => mk(h, widths[i], true)) }),
           ...rows.map(r => new TableRow({ cantSplit: true, children: r.map((c, i) => mk(c, widths[i], false)) }))] });
}
const gap = () => new Paragraph({ spacing: { after: 80 }, children: [] });

const C = [];   // content
// ---------------------------------------------------------------- title
C.push(new Paragraph({ bidirectional: true, spacing: { before: 200, after: 80 }, children: [new TextRun({ text: "دليل استخدام Smart Route", font: FONT, rightToLeft: true, bold: true, size: 56, color: BLUE })] }));
C.push(new Paragraph({ bidirectional: true, spacing: { after: 60 }, children: [new TextRun({ text: "إضافة سوليد ووركس لتخطيط مسارات الكابلات حوالين الشكل الفعلي للمجسمات", font: FONT, rightToLeft: true, size: 28, color: "404040" })] }));
C.push(new Paragraph({ bidirectional: true, spacing: { after: 200 }, children: [new TextRun({ text: "الإصدار 0.3.0 (Beta)", font: FONT, rightToLeft: true, size: 24, color: "7F7F7F" })] }));
C.push(note("tip", "الصور في الدليل **رسومات توضيحية** مطابقة لتصميم شاشات الأداة، مش لقطات شاشة من سوليد ووركس، وشكل برنامجك (الألوان والأيقونات) ممكن يختلف شوية. شاشة المعاينة (شكل 7) اتحسبت **فعليًا بمحرك الأداة** على مشهد تجريبي: حيطة بين كونكتورين. ملف Word ده قابل للتعديل، فبعد أول تشغيل تقدر تستبدل الصور بلقطات حقيقية."));
C.push(note("warn", "الأداة لسه **Beta**: اتجرب منطقها بالاختبارات الآلية، لكن لسه ما اتجربتش على سوليد ووركس حقيقي. ابدأ بالقسم 4 (Scan Routes) وابعت تقرير أي مشكلة (القسم 14)."));

// ---------------------------------------------------------------- 1
C.push(H1("1. الأداة بتعمل إيه؟"));
C.push(P("Smart Route إضافة (Add-in) بتشتغل جوه سوليد ووركس جنب أوامر الروتينج (Routing). بتساعدك ترسم مسار الكابل بين نقطتين بحيث يمشي **حوالين المجسمات الفعلية** مش من جواها، ويحترم **أقل نصف قطر انحناء** للكابل و**مسافة أمان**."));
["بتحسب المسار على **الشكل الفعلي** للمجسمات (مش مربعات حواليها).", "بتعرض لك لحد **3 بدائل** في معاينة 3D قبل ما تنشئ أي حاجة.", "بتنشئ **الراوت الحقيقي** في Routing بعد موافقتك.", "بتتحقق بعد الإنشاء من **نصف قطر الانحناء والمسافات والتداخل**.", "بتراجع الراوتات الموجودة وتقترح مسارات أقصر."].forEach(t => C.push(B(t)));

// ---------------------------------------------------------------- 2
C.push(H1("2. التسطيب"));
C.push(H2("2.1 المتطلبات"));
["Windows 64-bit.", "سوليد ووركس مثبّت، وإضافة **SOLIDWORKS Routing** متاحة عندك.", "صلاحيات Administrator أثناء التسطيب بس.", "مفيش حاجة تانية تسطّبها (المحرك متضمّن جوه المُثبّت، ومش محتاج بايثون)."].forEach(t => C.push(B(t)));
C.push(H2("2.2 خطوات التسطيب"));
steps(["نزّل ملف `SmartRoute-Setup-x.y.z.exe` من صفحة Releases في GitHub بتاعة المشروع.", "اقفل سوليد ووركس.", "اضغط على الملف مرتين ووافق على رسالة Windows لصلاحيات الـ Administrator.", "كمّل **Next ← Next ← Install ← Finish** (شكل 1). لو المُثبّت طلب قفل سوليد ووركس وافق."]).forEach(x => C.push(x));
C.push(...fig("fig_installer", "شاشات المُثبّت: (1) ترحيب (2) مكان التسطيب، سيبه كما هو (3) Install (4) Finish", 600));
C.push(H2("2.3 التفعيل داخل سوليد ووركس (مرة واحدة)"));
steps(["افتح سوليد ووركس.", "من القايمة: **Tools ← Add-Ins...**", "علّم على **Smart Route** في عمودين: Active و Start Up (1). وتأكد إن **SOLIDWORKS Routing** معلّم كمان (2).", "اضغط **OK**."]).forEach(x => C.push(x));
C.push(...fig("fig_addins", "نافذة Add-Ins: (1) Smart Route (2) SOLIDWORKS Routing", 520));
C.push(P("عمود **Start Up** معناه إن الإضافة تفتح لوحدها في كل مرة، فمش هتعمل الخطوات دي تاني. افتح أسمبلي وهتلاقي تبويب **Smart Route** (القسم 3)."));

// ---------------------------------------------------------------- 3
C.push(H1("3. شكل الأداة داخل سوليد ووركس"));
C.push(P("بعد التفعيل، في أي **أسمبلي** هيظهر تبويب جديد اسمه **Smart Route** في الـ CommandManager (شكل 3). الأيقونات حروف ملوّنة (S, R, V, A, W, U)."));
C.push(...fig("fig_tab", "تبويب Smart Route بأزراره الستة", 640));
C.push(table(["#", "الزر", "بيعمل إيه"], [
  ["1", "Smart Auto Route", "الزر الأساسي: يخطط مسار حوالين المجسمات وينشئ الراوت (القسم 5)."],
  ["2", "Scan Routes", "يقرا كل الراوتات في الأسمبلي ويكتب تقرير. استخدمه كاختبار أول (القسم 4)."],
  ["3", "Review Routes", "يراجع الراوتات الموجودة ويقترح الأقصر (القسم 8)."],
  ["4", "Accuracy", "يتحكم في السرعة والدقة (القسم 7)."],
  ["5", "Auto Watch", "يراقب تعديلات الأسمبلي ويراجع تلقائيًا (القسم 9)."],
  ["6", "Updates", "يشوف لو في نسخة أحدث (القسم 10)."],
], [700, 2600, 6338]));
C.push(gap());
C.push(note("tip", "التبويب بيظهر في **الأسمبلي** بس، مش في الباتر أو الدرافت."));

// ---------------------------------------------------------------- 4
C.push(H1("4. أول تجربة: Scan Routes"));
C.push(P("قبل أي حاجة، تأكد إن الأداة بتقرا الراوتات بتاعتك:"));
steps(["افتح أسمبلي فيه راوت واحد على الأقل.", "اضغط **Scan Routes**.", "هتظهر رسالة بعدد الراوتات اللي اتقرت، وتقرير كامل في الملف `%APPDATA%\\SmartRoute\\scan.txt` (الصق المسار في شريط عنوان الـ Explorer)."]).forEach(x => C.push(x));
C.push(note("warn", "لو الرسالة قالت **صفر راوتات** والأسمبلي فيه راوتات فعلًا، يبقى القراءة مش شغالة على ملفاتك. ابعت `scan.txt` و `smartroute.log` للمطوّر عشان يظبطها."));

// ---------------------------------------------------------------- 5
C.push(H1("5. Smart Auto Route خطوة بخطوة"));
C.push(P("المراحل بشكل عام (شكل 4). أهم حاجة: **مفيش أي تغيير بيحصل في سوليد ووركس غير لما تضغط Create route**."));
C.push(...fig("fig_flow", "مراحل الاستخدام", 640));
C.push(H2("5.1 جهّز الراوت واختار النقطتين"));
steps(["ابدأ الراوت بالطريقة المعتادة في Routing (مثلًا Start by Drag من كونكتور) وادخل **Edit Route** بحيث الـ 3D Sketch بتاع الراوت يبقى هو المفتوح.", "اختار **نقطة البداية** (1) بالماوس، وبعدين اضغط **Ctrl** واختار **نقطة النهاية** (2). المفروض النقطتين يكونوا نقاط في الـ 3D Sketch عند الكونكتورين."]).forEach(x => C.push(x));
C.push(...fig("fig_select", "(1) نقطة البداية (2) نقطة النهاية. الخط البرتقالي المتقطع هو الخط المستقيم اللي كان هيتعمل وبيعدّي في الحيطة، وSmart Route بتخطط حواليها", 600));
C.push(note("tip", "لو اخترت نقطتين من نوع تاني (Vertex مثلًا)، الأداة بتستخدم مكانهم وتنشئ نقاط جديدة في الـ Sketch المفتوح، بشرط تكون في وضع **Edit Route**."));
C.push(H2("5.2 اضغط Smart Auto Route واملأ البيانات"));
C.push(...fig("fig_dialog", "شاشة بيانات السلك", 430));
C.push(table(["#", "الخانة", "معناها"], [
  ["1", "Wire name", "اسم للسلك (علشان تميّزه بس)."],
  ["2", "Cable diameter (mm)", "قطر الكابل بالمللي من داتاشيت الكابل."],
  ["3", "Min bend radius (mm)", "أقل نصف انحناء مسموح. لو سوليد ووركس قدر يقراه من خصائص الراوت هتلاقي جنبه \"from route\". قاعدة عامة: من 4 لـ 10 أضعاف القطر حسب الكابل."],
  ["4", "Wanted length (mm)", "اختياري. سيبه فاضي = أقصر مسار، أو اكتب طول محدد (القسم 6)."],
  ["5", "Safety clearance (mm)", "أقل مسافة بين سطح الكابل والمجسمات. الافتراضي 5."],
  ["6", "Route", "يبدأ الحساب."],
], [700, 2900, 6038]));
C.push(gap());
C.push(P("القيم اللي بتكتبها بتتحفظ، فالمرة الجاية هتلاقيها جاهزة."));
C.push(H2("5.3 الحساب"));
C.push(P("الحساب بيشتغل في الخلفية وسوليد ووركس بيفضل شغال، وفي شريط الحالة بتظهر رسالة \"planning\". **أول مرة** (وبعد تغيير الدقة) بياخد وقت أطول لأنه بيقرا المجسمات. بعد كده بيستخدم المحفوظ ويقرا بس اللي اتغيّر."));
C.push(H2("5.4 المعاينة"));
C.push(P("بعد الحساب بتظهر شاشة المعاينة (شكل 7). **لحد هنا مفيش أي حاجة اتعملت في سوليد ووركس.**"));
C.push(...fig("fig_preview", "شاشة المعاينة (محسوبة بمحرك الأداة على مشهد تجريبي): (1) عرض 3D (2) قايمة البدائل (3) تفاصيل البديل المختار (4) Create route / Cancel", 640));
C.push(...[
  "**عرض 3D (1):** اسحب بالماوس للدوران، عجلة الماوس للتكبير، سحب بالزر اليمين للتحريك، دبل كليك لإعادة الضبط.",
  "**النقط الرمادية والمربعات الخفيفة:** المجسمات القريبة (الشكل الفعلي). **النقطة الخضراء** = البداية، **الحمراء** = النهاية.",
  "**الخط الأزرق السميك** = البديل المختار، و**المتقطع** = البدائل التانية.",
].map(B));
C.push(H2("البدائل الثلاثة"));
C.push(table(["البديل", "المعنى"], [
  ["Shortest (free angles)", "أقصر طول: بزوايا حرة ومنحنى ناعم (يتنشئ بوضع Flexible)."],
  ["Neat (right angles)", "زوايا قائمة، شكل منظّم يشبه الراوتات المعتادة (وضع Orthogonal)، غالبًا أطول."],
  ["Extra clearance", "أبعد عن المجسمات بمسافة أمان أكبر."],
], [3000, 6638]));
C.push(gap());
C.push(H2("إزاي تقرا التفاصيل"));
C.push(table(["البند", "معناه"], [
  ["Length / bends", "الطول وعدد الانحناءات."],
  ["min bend radius", "أصغر نصف انحناء في المسار. لازم يكون **أكبر من أو يساوي** المطلوب (need)."],
  ["min clearance", "أقل مسافة بين سطح الكابل والمجسمات الفعلية."],
  ["collisions", "عدد أماكن التصادم. لازم **0**."],
  ["tight spots", "أماكن أقرب من مسافة الأمان اللي كتبتها (لكن مش تصادم)."],
  ["bend problems", "أماكن نصف القطر فيها أقل من المطلوب."],
  ["Status: OK / check!", "OK = مفيش مشاكل. **check!** (بالأحمر) = فيه تصادم أو مشكلة انحناء، والأداة بتسألك تأكيد قبل الإنشاء."],
], [2800, 6838]));
C.push(gap());
C.push(note("warn", "اختار بديل حالته **OK**. لو كلهم check!: جرّب تقليل مسافة الأمان، أو تقليل نصف القطر لو الكابل يسمح، أو زيادة الدقة (القسم 7)."));
C.push(H2("5.5 الإنشاء والتحقق"));
steps(["اضغط **Create route** (أو **Cancel** وما يتغيّرش أي حاجة).", "الأداة بتضيف نقاط المسار في الـ 3D Sketch وتستدعي أمر Routing لإنشاء الراوت (منحنى ناعم لـ Shortest و Extra clearance، وزوايا قائمة لـ Neat).", "بعد الإنشاء بتتقرا الراوت الفعلي وتظهر **رسالة التحقق** (شكل 8)."]).forEach(x => C.push(x));
C.push(...fig("fig_after", "رسالة التحقق: (1) ملخص الإنشاء، Ctrl+Z بيلغي (2) الطول (3) أقل نصف انحناء (4) أقل مسافة للمجسمات + تقرير تداخل سوليد ووركس", 560));
C.push(P("لو في مشكلة بتظهر الرسالة بعلامة تحذير وفيها **إحداثيات كل مكان بالمللي** (شكل 9). روح للمكان وظبّطه يدويًا، أو اعمل **Ctrl+Z** وجرّب بديل تاني."));
C.push(...fig("fig_after_bad", "مثال لرسالة فيها مشكلة (أرقام توضيحية)", 560));
C.push(note("tip", "لو ظهرت رسالة **\"The automatic route call failed\"**: النقط اتحطت في الـ Sketch فعلًا، شغّل **Auto Route العادي** عليها."));

// ---------------------------------------------------------------- 6
C.push(H1("6. الطول المطلوب (Wanted length)"));
["سيب الخانة **فاضية** = أقصر مسار.", "اكتب طول (مثلًا `1900`) = الأداة تضيف **انحناءة جانبية (حرف U)** في أطول جزء مستقيم عشان توصل للطول بدقة حوالي ±1 مم، مع احترام نصف الانحناء والمسافة.", "لو الطول أقل من أقصر مسار ممكن: بتستخدم الأقصر وتكتبلك ملاحظة.", "لو مفيش مكان للزيادة: بتديك **أقرب طول ممكن** وتكتب الطول الفعلي.", "الطول المقصود هو طول **الخط المركزي** للراوت."].forEach(t => C.push(B(t)));

// ---------------------------------------------------------------- 7
C.push(H1("7. الدقة (Accuracy)"));
C.push(P("زر **Accuracy** بيحدد حجم خلية الشبكة اللي بتحسب عليها الأداة. **كل ما الخلية أصغر، النتيجة أدق والوقت أطول**."));
C.push(...fig("fig_accuracy", "شاشة الدقة: (1) المستوى (2) أو حجم خلية مخصص بالمللي", 420));
C.push(table(["المستوى", "حجم الخلية", "استخدامه"], [
  ["1 - Draft", "20 مم", "تجارب سريعة جدًا ومساحات كبيرة."],
  ["2 - Fast", "10 مم", "مراجعة سريعة."],
  ["3 - Normal (الافتراضي)", "5 مم", "توازن كويس بين السرعة والدقة."],
  ["4 - Fine", "2.5 مم", "أماكن ضيقة وتفاصيل صغيرة."],
  ["5 - Ultra", "1.5 مم", "أعلى دقة، وأبطأ بكتير."],
  ["Custom", "اكتب الرقم", "مثلًا `3mm`."],
], [3000, 2000, 4638]));
C.push(gap());
C.push(P("أمثلة تقريبية للوقت على مشهد تجريبي بسيط (سلك 1 متر حوالين حيطة): Draft حوالي ثانية، Fast حوالي ثانية ونص، Normal حوالي 4-5 ثواني، Fine حوالي 24 ثانية. الأرقام هتتغيّر حسب الأسمبلي وجهازك."));
["بعد تغيير الدقة بيعيد معالجة المجسمات **المحفوظة** من غير قراءة جديدة من سوليد ووركس.", "لو الأسمبلي كبير جدًا والدقة عالية، الأداة بتكبّر الخلية تلقائيًا وتكتب ملاحظة (cell coarsened) عشان الذاكرة."].forEach(t => C.push(B(t)));
C.push(note("tip", "ابدأ بـ **Normal**. استخدم **Draft** للتجريب السريع، و**Fine** لما المكان ضيق."));

// ---------------------------------------------------------------- 8
C.push(H1("8. مراجعة الراوتات (Review Routes)"));
steps(["اضغط **Review Routes**.", "الأداة بتعيد تخطيط كل راوت (والباقي بيتحسب عوائق ثابتة) وبتعرض اللي ينفع يقصر أكتر من 2% وبدون مشاكل (شكل 11).", "اختار صف واضغط **Draw selected as 3D sketch**: بيرسم الاقتراح كـ 3D Sketch في الأسمبلي باسم `SmartRoute_Suggest_...` عشان تقارنه.", "لو عجبك، أعد عمل الراوت بـ Smart Auto Route أو يدويًا."]).forEach(x => C.push(x));
C.push(...fig("fig_review", "قايمة الاقتراحات: (1) الراوتات وتوفير الطول (2) رسم الاقتراح", 560));
C.push(note("tip", "**مفيش حاجة بتتغيّر في الأسمبلي تلقائيًا.** المراجعة للراوتات الفردية (بدون تفريعات) بس، وبتستخدم آخر قطر وأقل انحناء كتبتهم في شاشة Smart Auto Route."));

// ---------------------------------------------------------------- 9
C.push(H1("9. المراقبة التلقائية (Auto Watch)"));
C.push(P("اضغط **Auto Watch** لتشغيلها (ونفس الزر للإيقاف). بعد أي تعديل في الأسمبلي وبعد **5 ثواني هدوء** بتقرا الأداة المجسمات اللي اتغيّرت بس وتراجع الراوتات. لو لقت أحسن بتظهر قايمة الاقتراحات (زي القسم 8)، ولو مفيش مش بتظهر حاجة."));
C.push(note("tip", "شغّلها وانت بتعدّل في تصميم شبه ثابت. لو بتعدّل كتير وبتزعجك، اقفلها."));

// ---------------------------------------------------------------- 10
C.push(H1("10. التحديث (Updates)"));
C.push(P("زر **Updates** بيشوف أحدث إصدار على GitHub. وكمان بيتشيّك **تلقائيًا مرة كل 24 ساعة** بعد حوالي 20 ثانية من فتح سوليد ووركس. لو في نسخة جديدة بتظهر رسالة فيها ملاحظات الإصدار (شكل 12):"));
C.push(...fig("fig_update", "رسالة نسخة جديدة", 520));
["**Yes:** بينزّل الـ Setup وبيشغّله تلقائيًا **بعد ما تقفل سوليد ووركس** (هتظهر رسالة الصلاحيات).", "**No:** تتجاهل التحديث."].forEach(t => C.push(B(t)));
C.push(note("bad", "التحديث التلقائي شغّال بس لو صاحب المشروع نشر الإصدارات على GitHub في Repo **عام (Public)**."));

// ---------------------------------------------------------------- 11
C.push(H1("11. أماكن الملفات"));
C.push(table(["الملف", "فيه إيه"], [
  ["`C:\\Program Files\\SmartRoute`", "مكان التسطيب (الإضافة والمحرك)."],
  ["`%APPDATA%\\SmartRoute\\settings.json`", "إعداداتك: القطر، الانحناء، المسافة، الدقة، المراقبة."],
  ["`%APPDATA%\\SmartRoute\\smartroute.log`", "سجل الأخطاء. ابعته لو حصلت مشكلة."],
  ["`%APPDATA%\\SmartRoute\\scan.txt`", "تقرير Scan Routes."],
  ["`<اسم الأسمبلي>_geom.cache`", "ذاكرة المجسمات جنب الأسمبلي (بتتعمل تلقائيًا). امسحه لو عايز قراءة جديدة من الأول."],
], [4300, 5338]));
C.push(gap());
C.push(P("**الإزالة:** Windows Settings ← Apps ← **Smart Route for SOLIDWORKS** ← Uninstall."));

// ---------------------------------------------------------------- 12
C.push(H1("12. مشاكل شائعة وحلولها"));
C.push(table(["المشكلة / الرسالة", "السبب والحل"], [
  ["تبويب Smart Route مش ظاهر", "تأكد إن الإضافة معلّمة في Tools ← Add-Ins، وإن في **أسمبلي** مفتوح. لو لسه، شوف `smartroute.log`."],
  ["Could not start the planning engine", "ملف المحرك مش موجود (`engine\\SmartRouteEngine.exe`). أعد التسطيب."],
  ["Select the two end points...", "اختار نقطتين قبل الضغط على Smart Auto Route (الثانية بـ Ctrl)."],
  ["Could not add sketch points. Edit the route's 3D sketch...", "مش في وضع **Edit Route**. ادخل الراوت وأعد المحاولة."],
  ["No route could be planned: no path", "مفيش طريق بالإعدادات دي. قلّل مسافة الأمان أو نصف القطر، أو غيّر الدقة، وتأكد إن النقطتين مش جوه مجسم مقفول."],
  ["search too heavy for this accuracy level", "الحساب تقيل. قلّل الدقة (زر Accuracy)."],
  ["check! في المعاينة / PROBLEM في التقرير", "فيه تصادم أو نصف انحناء أقل من المطلوب. اختار بديل تاني أو غيّر الإعدادات."],
  ["The automatic route call failed", "النقط اتحطت في الـ Sketch. شغّل Auto Route العادي عليها."],
  ["Could not check for updates", "مفيش إنترنت، أو الـ Repo خاص (Private) أو مش مضبوط."],
  ["الحساب بطيء", "قلّل الدقة. أول مرة بتقرا كل المجسمات. استخدم Draft للتجريب."],
], [3900, 5738]));
C.push(gap());

// ---------------------------------------------------------------- 13
C.push(H1("13. نصائح لنتيجة أفضل"));
["احفظ ملف الأسمبلي قبل أول تجربة.", "ابدأ بدقة **Normal** وراجع المعاينة. لو المكان ضيق انتقل لـ **Fine**.", "اختار نقطتي النهاية بدقة على الكونكتورين.", "لو عندك أسلاك كتير، اعملهم **واحد ورا التاني**: الأسلاك اللي اتعملت قبل كده بتتحسب عوائق صلبة للسلك الجاي.", "حافظ على قيمة صحيحة لأقل نصف انحناء من داتاشيت الكابل.", "في الآخر شغّل دايمًا **Evaluate ← Interference Detection** من سوليد ووركس. الشبكة تقريبية والتحقق بتاع الأداة مش بديل عنه."].forEach(t => C.push(B(t)));

// ---------------------------------------------------------------- 14
C.push(H1("14. حدود الأداة والإبلاغ عن مشكلة"));
["**Beta:** لسه ما اتجربتش على سوليد ووركس حقيقي. أماكن الاحتمال الأكبر لأي خلل: قراءة الراوتات، وإنشاء الراوت بأمر Routing.", "الدقة = حجم الخلية. تفاصيل أصغر منها ممكن تتفوّت، وده سبب أهمية التحقق وInterference Detection.", "التفريعات (Harness) لسه مش بتتراجع، وقطر الأسلاك القديمة هو آخر قطر كتبته.", "الأداة مساعدة هندسية: راجع النتيجة بنفسك."].forEach(t => C.push(B(t)));
C.push(P("**لو حصلت مشكلة:** ابعت الملفين `smartroute.log` و `scan.txt` (القسم 11) مع وصف بسيط للي عملته والرسالة اللي ظهرت."));

// ---------------------------------------------------------------- build
const doc = new Document({
  creator: "Smart Route", title: "دليل استخدام Smart Route",
  styles: { default: { document: { run: { font: FONT, size: 24 } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 32, bold: true, font: FONT, color: BLUE }, paragraph: { spacing: { before: 360, after: 160 }, outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { size: 27, bold: true, font: FONT, color: ACC }, paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 } } ] },
  numbering: { config: [{ reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "\u2022", alignment: AlignmentType.START, style: { paragraph: { indent: { left: 540, hanging: 360 } } } }] }, ...stepCfg] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: "Smart Route - دليل الاستخدام - صفحة ", font: FONT, size: 18, color: "7F7F7F", rightToLeft: true }), new TextRun({ children: [PageNumber.CURRENT], font: FONT, size: 18, color: "7F7F7F" })] })] }) },
    children: C }],
});
Packer.toBuffer(doc).then(b => { fs.writeFileSync("/tmp/guide/SmartRoute-UserGuide-ar.docx", b); console.log("written", b.length); });
