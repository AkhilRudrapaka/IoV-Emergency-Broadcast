// Builds the panel presentation as an editable PowerPoint deck (16:9, 25 slides).
// Every number comes from generated/pptx_data.json (made by make_pptx_data.py from the experiment CSVs);
// every picture is a genuine capture or crop from figures/. Charts and tables are native PowerPoint objects.
//
//   NODE_PATH=<folder with pptxgenjs> node final_panel_review/scripts/make_pptx.js <out.pptx> <apply_theme.js>
"use strict";
const fs = require("fs");
const path = require("path");
const pptxgen = require("pptxgenjs");

const ROOT = path.resolve(__dirname, "..");
const FIG = path.join(ROOT, "figures");
const D = JSON.parse(fs.readFileSync(path.join(ROOT, "generated", "pptx_data.json"), "utf8"));
const REFS = JSON.parse(fs.readFileSync(path.join(ROOT, "generated", "pptx_refs.json"), "utf8"))
	.map((r) => r.replace(/\s+I{1,2}$/, "").trim());
const OUT = process.argv[2];
const { applyTheme } = require(process.argv[3]);
const M = D.macros;

const THEME = {
	name: "Amrita IoV Panel",
	headFontFace: "Calibri",
	bodyFontFace: "Calibri",
	colors: {
		dk1: "1F2328", lt1: "FFFFFF", dk2: "7A0E2F", lt2: "F3F4F6",
		accent1: "A4123F", accent2: "1B7F4B", accent3: "1F5FA0", accent4: "C62828", accent5: "B45F06", accent6: "5B6470",
		hlink: "1F5FA0", folHlink: "7A0E2F",
	},
};
const HEX = THEME.colors;
// light tints (hex only) and neutral lines
const T = { green: "E8F4EC", blue: "E7EFF8", red: "FBEAEA", maroon: "F7E8ED", gray: "F3F4F6", amber: "FBF1E6", line: "D0D5DB",
	slate: "37474F", mute: "6B7280", car: "BFC8D6", carLine: "8A94A6", road: "DDE1E6" };

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.333 x 7.5 in
pres.theme = { headFontFace: THEME.headFontFace, bodyFontFace: THEME.bodyFontFace };
pres.author = "Team 83";
pres.company = "Amrita Vishwa Vidyapeetham";
pres.title = "Emergency Message Dissemination for Broadcast Storm Mitigation in the Internet of Vehicles";
const C = pres.SchemeColor;
const S = { ink: C.text1, white: C.background1, maroon: C.accent1, green: C.accent2, blue: C.accent3, red: C.accent4,
	amber: C.accent5, gray: C.accent6 };
const W = 13.333, L = 0.55, CW = 12.233;

// ------------------------------------------------------------------ layouts
pres.defineSlideMaster({
	title: "TITLE",
	background: { color: HEX.lt1 },
	objects: [],
});
pres.defineSlideMaster({
	title: "CONTENT",
	background: { color: HEX.lt1 },
	margin: [0.5, 0.55, 0.5, 0.55],
	objects: [
		{ rect: { x: 0, y: 0, w: W, h: 1.0, fill: { color: C.accent1 }, line: { type: "none" } } },
		{ placeholder: { options: { name: "title", type: "title", x: L, y: 0.08, w: CW, h: 0.84, fontSize: 30, bold: true,
			color: C.background1, valign: "middle", align: "left", margin: 0 }, text: "" } },
		{ text: { text: "Team 83  ·  Emergency Message Dissemination for Broadcast Storm Mitigation in the IoV",
			options: { x: L, y: 7.08, w: 9, h: 0.3, fontSize: 10, color: C.accent6, margin: 0 } } },
	],
	slideNumber: { x: 12.13, y: 7.08, w: 0.65, h: 0.3, fontSize: 10, color: HEX.accent6, align: "right" },
});
pres.defineSlideMaster({
	title: "CLOSING",
	background: { color: HEX.accent1 },
	objects: [],
});

// ------------------------------------------------------------------ helpers
let slideNo = 0;
let section = "";
function sect(title) { section = title; pres.addSection({ title }); }
function content(title, notes) {
	slideNo += 1;
	const s = pres.addSlide({ masterName: "CONTENT", sectionTitle: section });
	s.addText(`${slideNo}. ${title}`, { placeholder: "title" });
	if (notes) s.addNotes(notes);
	return s;
}
function txt(s, text, o) {
	s.addText(text, Object.assign({ isTextBox: true, margin: 0, fontSize: 16, color: S.ink, valign: "top",
		fontFace: THEME.bodyFontFace }, o));
}
function shadow() { return { type: "outer", color: "000000", opacity: 0.12, blur: 4, offset: 1.5, angle: 90 }; }
function card(s, x, y, w, h, fill, line, o = {}) {
	s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y, w, h, rectRadius: o.r === undefined ? 0.08 : o.r,
		fill: { color: fill }, line: line ? { color: line, width: o.lw || 1 } : { type: "none" },
		shadow: o.shadow ? shadow() : undefined, objectName: o.name });
}
function circleNum(s, n, cx, cy, d, color, size) {
	s.addText(String(n), { shape: pres.shapes.OVAL, x: cx - d / 2, y: cy - d / 2, w: d, h: d, fill: { color },
		line: { type: "none" }, color: S.white, bold: true, fontSize: size || 16, align: "center", valign: "middle",
		margin: 0 });
}
function line(s, x1, y1, x2, y2, color, o = {}) {
	s.addShape(pres.shapes.LINE, { x: Math.min(x1, x2), y: Math.min(y1, y2), w: Math.max(Math.abs(x2 - x1), 0.001),
		h: Math.max(Math.abs(y2 - y1), 0.001), flipH: x2 < x1, flipV: y2 < y1,
		line: { color, width: o.w || 1.5, dashType: o.dash || "solid", endArrowType: o.arrow ? "triangle" : undefined } });
}
function img(s, file, x, y, w, h, o = {}) {
	if (o.frame) s.addShape(pres.shapes.RECTANGLE, { x: x - 0.03, y: y - 0.03, w: w + 0.06, h: h + 0.06,
		fill: { color: HEX.lt1 }, line: { color: o.frame, width: o.fw || 1 } });
	s.addImage({ path: path.join(FIG, file), x, y, w, h, altText: o.alt || file });
}
function imgH(file, h) { const [pw, ph] = D.images[file]; return h * pw / ph; }
// a labelled callout on an image: ring at relative (rx, ry) measured from the image's bottom-left (as in the report)
function ring(s, im, rx, ry, rRel) {
	const d = 2 * rRel * im.h;
	s.addShape(pres.shapes.OVAL, { x: im.x + rx * im.w - d / 2, y: im.y + (1 - ry) * im.h - d / 2, w: d, h: d,
		fill: { type: "none" }, line: { color: HEX.accent1, width: 2.5 } });
}
function callout(s, im, label, ax, ay, anchor, targets, w) {
	const h = 0.38, px = im.x + ax * im.w, py = im.y + (1 - ay) * im.h;
	const x = anchor === "ne" ? px - w : px - w / 2, y = anchor === "s" ? py - h : py;
	s.addText(label, { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06, x, y, w, h, fill: { color: HEX.lt1 },
		line: { color: HEX.accent1, width: 1.25 }, color: S.maroon, bold: true, fontSize: 14, align: "center",
		valign: "middle", margin: 0 });
	const sx = x + w / 2, sy = anchor === "s" ? y + h : y;
	for (const [tx, ty] of targets) line(s, sx, sy, im.x + tx * im.w, im.y + (1 - ty) * im.h, HEX.accent1, { w: 1.5 });
}
function takeaway(s, y, runs, h = 0.72, fill = T.maroon, lineC = HEX.accent1) {
	s.addText(runs, { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06, x: L, y, w: CW, h, fill: { color: fill },
		line: { color: lineC, width: 1 }, fontSize: 17, color: S.ink, valign: "middle", margin: [14, 14, 4, 4] });
}
const fmt = (v, dec) => v.toLocaleString("en-US", { minimumFractionDigits: dec, maximumFractionDigits: dec });
const A = D.at200;

// ================================================================== 1 Title
sect("Introduction");
{
	slideNo += 1;
	const s = pres.addSlide({ masterName: "TITLE", sectionTitle: section });
	s.addNotes("Introduce the team and the one-line idea: we built and tested a system that spreads accident alerts " +
		"quickly, with few copies, and only after trusted vehicles confirm them.");
	s.addText("Type 1: Research Project", { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06, x: 10.13, y: 0.25,
		w: 2.85, h: 0.46, fill: { color: C.accent1 }, line: { type: "none" }, color: S.white, bold: true, fontSize: 15,
		align: "center", valign: "middle", margin: 0 });
	const lw = 2.7;
	img(s, "../logo.png", (W - lw) / 2, 0.3, lw, lw * 568 / 1948, { alt: "Amrita Vishwa Vidyapeetham logo" });
	txt(s, "Emergency Message Dissemination for Broadcast Storm Mitigation in the Internet of Vehicles",
		{ x: 0.9, y: 1.2, w: W - 1.8, h: 1.3, fontSize: 34, bold: true, color: S.maroon, align: "center", valign: "middle",
			fontFace: THEME.headFontFace });
	s.addText("Domain: Network System and Security", { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06,
		x: (W - 4.6) / 2, y: 2.62, w: 4.6, h: 0.42, fill: { color: T.maroon }, line: { color: HEX.accent1, width: 1 },
		color: S.maroon, bold: true, fontSize: 15, align: "center", valign: "middle", margin: 0 });
	txt(s, [{ text: "23CSE498 – Project Phase II (External Review)", options: { bold: true } },
		{ text: "     |     ", options: { color: S.gray } }, { text: "Team Number: 83", options: { bold: true } }],
	{ x: 0.9, y: 3.2, w: W - 1.8, h: 0.4, fontSize: 18, align: "center" });
	const head = (t) => ({ text: t, options: { bold: true, color: S.white, fill: { color: C.accent1 }, align: "center" } });
	const rows = [[head("S.No"), head("Register Number"), head("Student Name")]];
	[["CB.SC.U4CSE23650", "Akhil Rudrapaka"], ["CB.SC.U4CSE23620", "G Nikshith"], ["CB.SC.U4CSE23332", "K Charan"],
		["CB.SC.U4CSE23640", "P Sreeshanth"], ["CB.SC.U4CSE23625", "K Chakri"]].forEach(([r, n], i) =>
		rows.push([{ text: String(i + 1), options: { align: "center" } }, { text: r, options: { align: "center" } },
			{ text: n }]));
	s.addTable(rows, { x: (W - 7.6) / 2, y: 3.75, w: 7.6, colW: [1.1, 3.3, 3.2], rowH: 0.36, fontSize: 16,
		color: S.ink, border: { type: "solid", pt: 0.75, color: T.line }, valign: "middle", margin: 4 });
	txt(s, [{ text: "Guide: " }, { text: "Dr. Radhika G", options: { bold: true } },
		{ text: ", Department of CSE, Amrita Vishwa Vidyapeetham" }],
	{ x: 0.9, y: 6.1, w: W - 1.8, h: 0.4, fontSize: 18, align: "center" });
	txt(s, "November 2026", { x: 0.9, y: 6.6, w: W - 1.8, h: 0.35, fontSize: 14, color: S.gray, align: "center" });
}

// ================================================================== 2 Guide approval
{
	const s = content("Guide Approval", "Show the guide's written approval for the external review and move on.");
	const w = 11.2, h = w * 426 / 981;
	img(s, "guide_approval_email.png", (W - w) / 2, 1.3, w, h, { frame: T.line,
		alt: "Screenshot of the guide's email reply: Approved for external review." });
	txt(s, [{ text: "Reply from the project guide, " }, { text: "Dr. Radhika G", options: { bold: true } },
		{ text: ", to the team's request for approval of the project report and presentation: " },
		{ text: "“Approved for external review.”", options: { bold: true, color: S.green } }],
	{ x: L, y: 6.35, w: CW, h: 0.6, fontSize: 17, align: "center" });
}

// ================================================================== 3 Introduction
{
	const s = content("Introduction: The Internet of Vehicles (IoV)",
		"Everything in this project is about one message type: the accident alert, sent vehicle to vehicle and " +
		"vehicle to roadside unit.");
	// schematic road
	card(s, 0.9, 1.55, 2.1, 0.5, HEX.lt1, T.carLine, { r: 0.06 });
	txt(s, "Traffic centre", { x: 0.9, y: 1.55, w: 2.1, h: 0.5, fontSize: 15, align: "center", valign: "middle" });
	line(s, 3.0, 1.8, 5.05, 1.8, T.mute, { w: 1.75 });
	s.addText("RSU", { shape: pres.shapes.RECTANGLE, x: 5.05, y: 1.55, w: 0.85, h: 0.5, fill: { color: C.accent1 },
		line: { type: "none" }, color: S.white, bold: true, fontSize: 15, align: "center", valign: "middle", margin: 0 });
	s.addShape(pres.shapes.RECTANGLE, { x: 5.43, y: 2.05, w: 0.09, h: 1.5, fill: { color: C.accent1 }, line: { type: "none" } });
	s.addShape(pres.shapes.RECTANGLE, { x: 0.7, y: 3.55, w: 5.9, h: 1.6, fill: { color: T.road }, line: { type: "none" } });
	line(s, 0.8, 4.35, 6.5, 4.35, HEX.lt1, { w: 2, dash: "dash" });
	const cars = [[1.2, 3.8], [2.75, 3.8], [4.35, 3.8], [1.3, 4.6], [3.0, 4.6], [5.4, 4.6]];
	cars.forEach(([x, y], i) => card(s, x, y, 0.62, 0.32, i === 2 ? "E53935" : T.car, i === 2 ? "B71C1C" : T.carLine,
		{ r: 0.05 }));
	s.addShape(pres.shapes.STAR_8_POINT || "star8", { x: 5.0, y: 3.62, w: 0.38, h: 0.38, fill: { color: "E53935" },
		line: { type: "none" } });
	line(s, 1.82, 3.96, 2.75, 3.96, HEX.accent3, { dash: "dash", w: 2 });
	line(s, 3.37, 3.96, 4.35, 3.96, HEX.accent3, { dash: "dash", w: 2 });
	line(s, 4.66, 4.12, 5.55, 4.6, HEX.accent3, { dash: "dash", w: 2 });
	txt(s, "V2V", { x: 1.9, y: 3.33, w: 0.8, h: 0.35, fontSize: 16, bold: true, color: S.blue });
	line(s, 4.66, 3.8, 5.3, 2.05, HEX.accent1, { dash: "dash", w: 2 });
	txt(s, "V2I", { x: 4.2, y: 2.75, w: 0.7, h: 0.35, fontSize: 16, bold: true, color: S.maroon });
	txt(s, "crashed vehicle", { x: 3.7, y: 5.25, w: 1.95, h: 0.35, fontSize: 15, bold: true, color: S.red, align: "center" });
	// three explanation rows
	const rows = [
		["V2V", HEX.accent3, S.blue, "Vehicle to vehicle (V2V)",
			"Nearby vehicles exchange short radio messages directly (IEEE 802.11p, Wi-Fi for vehicles) [17]."],
		["V2I", HEX.accent1, S.maroon, "Vehicle to roadside unit (V2I)",
			"Roadside units (RSUs) relay messages to the traffic centre."],
		["!", HEX.accent4, S.red, "Emergency alerts", "After a crash, vehicles behind must know within milliseconds."],
	];
	rows.forEach(([icon, hex, col, head, body], i) => {
		const y = 1.5 + i * 1.35;
		circleNum(s, icon, 7.35, y + 0.42, 0.78, hex, icon.length > 1 ? 15 : 24);
		txt(s, head, { x: 8.0, y, w: 4.8, h: 0.38, fontSize: 19, bold: true, color: col });
		txt(s, body, { x: 8.0, y: y + 0.42, w: 4.8, h: 0.75, fontSize: 16 });
	});
	takeaway(s, 6.0, [{ text: "Our focus: ", options: { bold: true } },
		{ text: "spread an accident alert quickly, with few copies, and only if it is genuine." }]);
}

// ================================================================== 4 Real-world problem
{
	const s = content("Real-World Problem: When Alerts Fail, Crashes Multiply",
		"These two chains are illustrative scenarios, not incidents we studied: V2X deployment is still limited, so we " +
		"show the mechanism and then measure it in simulation. Both a late alert and a fake alert cause the crashes the " +
		"system exists to prevent.");
	txt(s, "Illustrative scenarios", { x: L, y: 1.17, w: 4, h: 0.3, fontSize: 13, italic: true, color: S.gray });
	const scen = [
		["A late alert → secondary crashes", ["A crash is hidden from drivers behind", "The alert is lost among duplicate copies",
			"Drivers brake too late: pile-up"]],
		["A fake alert → panic braking", ["A dishonest vehicle sends a fake “crash ahead”", "No check: every vehicle believes it",
			"Sudden braking: rear-end crashes, jams"]],
	];
	scen.forEach(([head, steps], k) => {
		const x0 = L + k * 6.28;
		card(s, x0, 1.5, 5.95, 2.65, HEX.lt1, T.line, { shadow: true });
		txt(s, head, { x: x0 + 0.2, y: 1.6, w: 5.6, h: 0.42, fontSize: 19, bold: true, color: S.red });
		steps.forEach((t, i) => {
			const bx = x0 + 0.17 + i * 1.97;
			s.addText(t, { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06, x: bx, y: 2.18, w: 1.68, h: 1.75,
				fill: { color: i === 2 ? T.red : T.gray }, line: { color: i === 2 ? HEX.accent4 : T.line, width: 1 },
				fontSize: 15, color: S.ink, align: "center", valign: "middle", margin: [5, 5, 3, 3] });
			if (i < 2) line(s, bx + 1.7, 3.05, bx + 1.95, 3.05, T.mute, { arrow: true, w: 1.75 });
		});
	});
	card(s, L, 4.45, 5.95, 2.4, T.red, HEX.accent4);
	txt(s, "In our simulation: blind flooding, 200 vehicles, one alert", { x: L + 0.25, y: 4.58, w: 5.5, h: 0.35,
		fontSize: 15, bold: true, color: S.ink });
	[[fmt(A.flooding.transmissions[0], 1), "frames sent"], [fmt(Math.round(A.flooding.collision_losses[0]), 0),
		"lost receptions (copies destroyed in collisions)"]].forEach(([v, lab], i) => {
		const x = L + 0.25 + i * 2.85;
		txt(s, v, { x, y: 5.0, w: 2.7, h: 0.85, fontSize: 46, bold: true, color: S.red });
		txt(s, lab, { x, y: 5.85, w: 2.6, h: 0.85, fontSize: 15, color: S.ink });
	});
	card(s, L + 6.28, 4.45, 5.95, 2.4, T.gray, T.line);
	txt(s, "What is a broadcast storm? [1]", { x: L + 6.53, y: 4.58, w: 5.5, h: 0.4, fontSize: 19, bold: true, color: S.maroon });
	txt(s, "Every vehicle that hears the alert re-sends it. The copies collide on the one shared radio channel, so the " +
		"alert arrives late, or never.", { x: L + 6.53, y: 5.08, w: 5.5, h: 1.6, fontSize: 17 });
}

// ================================================================== 5 Problem statement
{
	const s = content("Problem Statement",
		"Two enemies: too many copies, and false copies. Both must be solved without making the alert late.");
	s.addText([
		{ text: "“To increase the emergency message dissemination in dense IoV networks more reliably by " },
		{ text: "reducing unnecessary rebroadcasting", options: { bold: true, color: S.maroon } },
		{ text: " and " },
		{ text: "preventing unverified alerts", options: { bold: true, color: S.maroon } },
		{ text: ".”" }],
	{ shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.08, x: 1.0, y: 1.45, w: W - 2.0, h: 1.85,
		fill: { color: T.maroon }, line: { color: HEX.accent1, width: 1.5 }, fontSize: 25, color: S.ink, align: "center",
		valign: "middle", margin: [24, 24, 8, 8] });
	const ch = [["Too many copies", "Every receiver re-sends the alert; copies collide and congest the channel."],
		["Unverified alerts", "One dishonest vehicle can raise a false alarm that spreads as fast as a real one."],
		["Late delivery", "The alert must still reach nearby vehicles and the roadside unit within milliseconds."]];
	ch.forEach(([h, b], i) => {
		const x = L + i * 4.19;
		card(s, x, 3.75, 3.85, 2.45, HEX.lt1, HEX.accent4, { shadow: true, lw: 1.25 });
		circleNum(s, i + 1, x + 0.5, 4.2, 0.56, HEX.accent4, 18);
		txt(s, h, { x: x + 0.95, y: 3.98, w: 2.8, h: 0.45, fontSize: 21, bold: true, color: S.red, valign: "middle" });
		txt(s, b, { x: x + 0.3, y: 4.72, w: 3.3, h: 1.35, fontSize: 17 });
	});
	txt(s, "IoV: Internet of Vehicles  ·  RSU: roadside unit", { x: L, y: 6.45, w: CW, h: 0.3, fontSize: 13, color: S.gray });
}

// ================================================================== 6 Motivation and novelty
{
	const s = content("Research Motivation and Novelty",
		"Our novelty is not a new primitive: it is combining trust, confirmation and controlled forwarding, then " +
		"measuring the gain against the strongest existing rule. Each novelty word is tied to a number we can defend.");
	const panels = [["Uncontrolled", "all 9 vehicles re-send", HEX.accent4, S.red], ["Controlled", "3 well-placed vehicles", HEX.accent2, S.green]];
	panels.forEach(([h, cap, hex, col], k) => {
		const x0 = L + k * 2.75;
		card(s, x0, 1.4, 2.55, 4.4, T.gray, T.line);
		txt(s, h, { x: x0, y: 1.52, w: 2.55, h: 0.4, fontSize: 18, bold: true, color: col, align: "center" });
		for (let r = 0; r < 3; r++) for (let c = 0; c < 3; c++) {
			const cx = x0 + 0.5 + c * 0.78, cy = 2.55 + r * 0.95;
			card(s, cx - 0.2, cy - 0.11, 0.4, 0.22, T.car, T.carLine, { r: 0.04 });
			const big = k === 1 && ((r === 0 && c === 1) || (r === 1 && c === 0) || (r === 2 && c === 2));
			if (k === 0 || big) {
				const d = k === 0 ? 0.68 : 0.92;
				s.addShape(pres.shapes.OVAL, { x: cx - d / 2, y: cy - d / 2, w: d, h: d, fill: { type: "none" },
					line: { color: "D97706", width: 1.75 } });
			}
		}
		txt(s, cap, { x: x0, y: 5.3, w: 2.55, h: 0.4, fontSize: 14, color: S.ink, align: "center" });
	});
	txt(s, "Fewer copies can lower reach; checking alerts adds delay. We measure both.",
		{ x: L, y: 6.0, w: 5.3, h: 0.75, fontSize: 15, italic: true, color: S.gray });
	const rx = 6.1, rw = W - L - rx;
	card(s, rx, 1.4, rw, 1.6, T.maroon, HEX.accent1);
	txt(s, "Motivation", { x: rx + 0.25, y: 1.5, w: 4, h: 0.42, fontSize: 20, bold: true, color: S.maroon });
	txt(s, "Improving security and speed by combining and optimizing different objectives such as trust and broadcasting.",
		{ x: rx + 0.25, y: 1.95, w: rw - 0.5, h: 0.95, fontSize: 17 });
	card(s, rx, 3.2, rw, 3.6, T.green, HEX.accent2);
	txt(s, "Novelty", { x: rx + 0.25, y: 3.3, w: 4, h: 0.42, fontSize: 20, bold: true, color: S.green });
	txt(s, "Enhancing existing algorithms from relevant research papers by measurable improvements in performance, " +
		"efficiency, and adaptability.", { x: rx + 0.25, y: 3.75, w: rw - 0.5, h: 0.95, fontSize: 17 });
	const ev = [["Performance", "fewer lost receptions in dense traffic (250–500 vehicles, significant)"],
		["Efficiency", `${M.NCutVsFlood} % fewer frames than blind flooding (200 vehicles)`],
		["Adaptability", "tested at 6 densities (50–500); higher measured reach in sparse traffic (50–100)"]];
	const evRuns = [];
	ev.forEach(([k, v], i) => evRuns.push({ text: k + ": ", options: { bold: true, color: S.green } },
		{ text: v, options: { breakLine: i < ev.length - 1 } }));
	txt(s, evRuns, { x: rx + 0.25, y: 4.75, w: rw - 0.5, h: 1.95, fontSize: 15, paraSpaceAfter: 6 });
}

// ================================================================== 7 Literature
sect("Literature and Research Gap");
{
	const s = content("Literature Survey: Four Families of Existing Work",
		"Each family solves one half of our problem: suppression limits copies but never checks the alert; trust " +
		"schemes check senders but do not limit copies.");
	const H = (t, fill) => ({ text: t, options: { bold: true, color: S.white, fill: { color: fill || C.accent1 } } });
	const plus = (t) => ({ text: "+ " + t, options: { color: S.green, bold: true } });
	const minus = (t) => ({ text: "− " + t, options: { color: S.red, bold: true } });
	const area = (t) => ({ text: t, options: { bold: true } });
	const rows = [[H("Research area"), H("What it does (key works)"), H("Strength", C.accent2), H("Gap", C.accent4)],
		[area("Broadcast suppression"), "Re-send with a probability [1]; farthest vehicle goes first [2, 3]; wait while disconnected [4]",
			plus("fewer duplicates"), minus("alert never checked")],
		[area("Trust and authentication"), "Combine several reports [5]; verify many signatures at once [6, 7]; vehicles rate neighbours [8]",
			plus("spots bad senders"), minus("copies not limited")],
		[area("Vehicle clustering"), "DBSCAN groups nearby vehicles and scores them [9]",
			plus("stable groups"), minus("no alert security")],
		[area("Route-based delivery"), "Route chosen by travel direction [10]",
			plus("less flooding"), minus("no neighbour confirmation")]];
	s.addTable(rows, { x: L, y: 1.35, w: CW, colW: [2.75, 5.2, 2.05, 2.233], rowH: [0.5, 1.0, 1.0, 0.8, 0.8],
		fontSize: 17, color: S.ink, border: { type: "solid", pt: 0.75, color: T.line }, valign: "middle", margin: 6 });
	takeaway(s, 5.95, [{ text: "Gap: ", options: { bold: true } },
		{ text: "none of the surveyed works both checks the alert and limits the copies." }]);
}

// ================================================================== 8 Research gap
{
	const s = content("Research Gap",
		"Our contribution is the integration and its measurement, not any single algorithm. The gap statement is " +
		"limited to the works we surveyed.");
	const g = [["Broadcast suppression", "fewer repeated messages", "alerts not checked"],
		["Trust and authentication", "spots untrusted senders", "repeats not limited"],
		["Vehicle clustering", "organises vehicles", "alerts not checked"],
		["Route-based forwarding", "reaches the infrastructure", "no neighbour confirmation"]];
	g.forEach(([h, ok, gap], i) => {
		const x = L + i * 3.128;
		card(s, x, 1.4, 2.85, 2.3, HEX.lt1, T.line, { shadow: true });
		txt(s, h, { x: x + 0.2, y: 1.52, w: 2.5, h: 0.72, fontSize: 18, bold: true, valign: "middle" });
		txt(s, [{ text: "✓ ", options: { color: S.green, bold: true } }, { text: ok }],
			{ x: x + 0.2, y: 2.3, w: 2.5, h: 0.62, fontSize: 16 });
		txt(s, [{ text: "✗ ", options: { color: S.red, bold: true } }, { text: gap }],
			{ x: x + 0.2, y: 2.95, w: 2.5, h: 0.62, fontSize: 16 });
		line(s, x + 1.425, 3.72, x + 1.425, 4.12, T.mute, { arrow: true, w: 1.75 });
	});
	card(s, L, 4.15, CW, 2.15, T.green, HEX.accent2, { lw: 1.25 });
	txt(s, "Our research direction: bring them together", { x: L, y: 4.25, w: CW, h: 0.45, fontSize: 20, bold: true,
		color: S.green, align: "center" });
	const chips = ["Trust evaluation", "Neighbour confirmation", "Controlled forwarding", "Roadside-unit delivery"];
	const cw = 2.55, gap = 0.42, x0 = L + (CW - (4 * cw + 3 * gap)) / 2;
	chips.forEach((t, i) => {
		const x = x0 + i * (cw + gap);
		s.addText(t, { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06, x, y: 4.85, w: cw, h: 0.62,
			fill: { color: HEX.lt1 }, line: { color: HEX.accent2, width: 1.25 }, color: S.green, bold: true, fontSize: 16,
			align: "center", valign: "middle", margin: 0 });
		if (i < 3) txt(s, "+", { x: x + cw, y: 4.85, w: gap, h: 0.62, fontSize: 24, bold: true, color: S.green,
			align: "center", valign: "middle" });
	});
	txt(s, "in one implemented and experimentally evaluated pipeline", { x: L, y: 5.65, w: CW, h: 0.4, fontSize: 17,
		align: "center" });
	txt(s, "Gap = across the works we surveyed (slide 7), not a claim that no one has ever combined these ideas.",
		{ x: L, y: 6.45, w: CW, h: 0.32, fontSize: 13, color: S.gray, italic: true });
}

// ================================================================== 9 Objectives
sect("Proposed System");
{
	const s = content("Project Objectives", "Each objective maps to the slide where we show it was met.");
	const ob = [["Build the pipeline", "City traffic → an alert recorded at a roadside unit (RSU)", "slides 11–12"],
		["Score vehicle trust", "From each vehicle's observed forwarding behaviour", "slide 13"],
		["Group trusted vehicles", "Trusted vehicles forward first for their group", "slide 13"],
		["Confirm every alert", "3 of 5 trusted neighbours must agree before it spreads", "slide 14"],
		["Fewer copies, fair test", "Compare with four baselines on identical traffic", "slides 15–19"]];
	ob.forEach(([h, b, sl], i) => {
		const y = 1.4 + i * 1.03;
		card(s, L, y, CW, 0.86, T.gray, undefined);
		circleNum(s, i + 1, L + 0.5, y + 0.43, 0.58, HEX.accent1, 18);
		txt(s, h, { x: L + 1.0, y, w: 3.6, h: 0.86, fontSize: 20, bold: true, color: S.maroon, valign: "middle" });
		txt(s, b, { x: L + 4.65, y, w: 5.6, h: 0.86, fontSize: 17, valign: "middle" });
		s.addText("→ " + sl, { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06, x: L + CW - 1.75, y: y + 0.21,
			w: 1.55, h: 0.44, fill: { color: HEX.lt1 }, line: { color: T.line, width: 1 }, fontSize: 14, color: S.gray,
			align: "center", valign: "middle", margin: 0 });
	});
}

// ================================================================== 10 Proposed solution
{
	const s = content("Proposed Solution in Five Steps",
		"Steps 4 and 5 only happen after step 3 succeeds: an alert that trusted neighbours do not confirm is never " +
		"forwarded.");
	const st = [["Evaluate vehicle behaviour", "Every vehicle gets a trust score"],
		["Group nearby trusted vehicles", "Trusted cluster heads forward first"],
		["Confirm the emergency alert", "3 of 5 trusted neighbours must agree"],
		["Forward only where needed", "Skip if every neighbour already has it"],
		["Deliver to the roadside unit", "The RSU verifies and records the alert once"]];
	const w = 2.15, step = 2.52;
	st.forEach(([h, b], i) => {
		const x = L + i * step;
		card(s, x, 1.5, w, 3.45, T.green, HEX.accent2, { shadow: true });
		circleNum(s, i + 1, x + w / 2, 1.95, 0.58, HEX.accent2, 18);
		txt(s, h, { x: x + 0.12, y: 2.4, w: w - 0.24, h: 1.15, fontSize: 18, bold: true, color: S.green, align: "center",
			valign: "middle" });
		line(s, x + 0.3, 3.65, x + w - 0.3, 3.65, "A7CDB6", { w: 1 });
		txt(s, b, { x: x + 0.12, y: 3.8, w: w - 0.24, h: 1.0, fontSize: 16, align: "center" });
		if (i < 4) line(s, x + w + 0.04, 3.22, x + step - 0.04, 3.22, T.mute, { arrow: true, w: 2 });
	});
	line(s, L + 3 * step, 5.18, L + 4 * step + w, 5.18, HEX.accent2, { w: 2 });
	txt(s, "only after step 3 succeeds", { x: L + 3 * step, y: 5.22, w: step + w, h: 0.35, fontSize: 14, italic: true,
		color: S.green, align: "center" });
	takeaway(s, 5.85, "The alert spreads with far fewer copies, and only after trusted vehicles confirm it.", 0.75,
		T.green, HEX.accent2);
}

// ================================================================== 11 Architecture
{
	const s = content("System Architecture: Five Implemented Stages",
		"Walk left to right: traffic and the crash, trust and clusters, the 3-of-5 check, controlled V2V forwarding, " +
		"then V2I delivery to the RSU. The bottom row is the path of one alert. Everything here is implemented; cloud " +
		"integration is future work on slide 21.");
	// figure drawn by scripts/make_architecture_final.py (3999 x 1725 px)
	const w = CW, h = w * 1725 / 3999;
	img(s, "../architecture/architecture_implemented.png", L, 1.2, w, h, {
		alt: "Five-stage architecture: traffic and emergency generation, trust evaluation and clustering, alert " +
			"verification, controlled dissemination, RSU processing and monitoring" });
	txt(s, "Implemented components only, checked against the source code. Algorithms: slide 17. Cloud integration is " +
		"proposed future work (slide 21).", { x: L, y: 1.2 + h + 0.1, w: CW, h: 0.35, fontSize: 13, color: S.gray,
		align: "center" });
}

// ================================================================== 12 One accident end to end
{
	const s = content("End-to-End Workflow: One Simulated Accident",
		"This is one genuine run from our simulator, not a mock-up: from the crash to the alert recorded at the " +
		"roadside unit took 22.5 ms.");
	const h = 5.3, w = imgH("view_map_walk_02_incident.png", h), im = { x: L, y: 1.25, w, h };
	img(s, "view_map_walk_02_incident.png", im.x, im.y, w, h, { frame: T.line,
		alt: "SUMO-GUI capture of the 5 by 5 city grid at the moment of the accident" });
	ring(s, im, 0.81, 0.707, 0.0385);
	callout(s, im, "accident", 0.98, 0.6, "ne", [[0.81, 0.672]], 1.25);
	callout(s, im, "RSU-2", 0.6, 0.16, "n", [[0.745, 0.25]], 1.0);
	txt(s, "Genuine SUMO-GUI capture [11]: 5×5 city grid, 200 vehicles.", { x: L, y: 6.62, w: w, h: 0.3, fontSize: 12,
		color: S.gray });
	const ev = [["t = 114 s", HEX.accent4, "A vehicle crashes; alert created"],
		["+0 ms", HEX.accent2, "Trust scores and groups ready"],
		["+7 ms", HEX.accent2, "2 of 5 confirmations in (3 needed)"],
		["+12.5 ms", HEX.accent2, "3 of 5 agree; certificate made; alert sent"],
		["+22.5 ms", HEX.accent1, "RSU-2 verifies and records it"],
		["+33 ms", HEX.accent2, "8 forwarders; 175 of 200 have it"],
		["+40.6 ms", HEX.accent2, "Trusted route also reaches RSU-2"],
		["after", HEX.accent6, "Results shown on the dashboard"]];
	const lx = 8.4, y0 = 1.5, dy = 0.58;
	s.addShape(pres.shapes.RECTANGLE, { x: lx - 0.02, y: y0, w: 0.04, h: dy * 7 + 0.1, fill: { color: T.line },
		line: { type: "none" } });
	ev.forEach(([t, hx, e], i) => {
		const y = y0 + 0.05 + i * dy;
		txt(s, t, { x: 6.55, y: y - 0.2, w: 1.6, h: 0.4, fontSize: 17, bold: true, color: hx, align: "right",
			valign: "middle" });
		s.addShape(pres.shapes.OVAL, { x: lx - 0.13, y: y - 0.13, w: 0.26, h: 0.26, fill: { color: hx },
			line: { color: HEX.lt1, width: 1.5 } });
		txt(s, e, { x: lx + 0.3, y: y - 0.2, w: W - L - lx - 0.3, h: 0.4, fontSize: 17, valign: "middle" });
	});
	s.addText([{ text: "In this genuine run, the verified alert was recorded at the RSU " },
		{ text: "22.5 ms", options: { bold: true } }, { text: " after the crash." }],
	{ shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06, x: 6.55, y: 6.05, w: W - L - 6.55, h: 0.72,
		fill: { color: T.maroon }, line: { color: HEX.accent1, width: 1 }, fontSize: 16, color: S.ink, valign: "middle",
		margin: [12, 12, 4, 4] });
}

// ================================================================== 13 Trust and grouping
{
	const s = content("Trust Evaluation and Vehicle Grouping",
		"A vehicle earns trust by actually forwarding. One bad act does not destroy trust; repeated bad acts do. " +
		"Groups come from DBSCAN with a 40 m radius.");
	const cards = [
		["Behaviour monitor", "watchdog [12]", [{ text: "Does each vehicle forward the messages it should?" }], 1.15],
		["Trust score", "Beta model [13]", [
			{ text: "trust = (good + 1) / (good + bad + 2)", options: { bold: true, fontSize: 19, color: S.green, breakLine: true } },
			{ text: "New vehicles start at 0.5; trusted at ≥ 0.7.", options: { breakLine: true } },
			{ text: "Example: 8 good, 1 bad → 9/11 = 0.82 → trusted", options: { italic: true } }], 2.0],
		["Grouping nearby vehicles", "DBSCAN [14]", [{ text: "Vehicles within 40 m of each other (at least 3) form a " +
			"group; its trusted cluster head (usually one) forwards first." }], 1.55]];
	let y = 1.3;
	cards.forEach(([h, tag, body, hh], i) => {
		card(s, L, y, 6.1, hh, i === 1 ? T.green : T.gray, i === 1 ? HEX.accent2 : T.line);
		txt(s, h, { x: L + 0.22, y: y + 0.1, w: 4.0, h: 0.4, fontSize: 19, bold: true, color: i === 1 ? S.green : S.ink });
		txt(s, tag, { x: L + 4.1, y: y + 0.14, w: 1.8, h: 0.35, fontSize: 12, color: S.gray, align: "right" });
		txt(s, body, { x: L + 0.22, y: y + 0.52, w: 5.7, h: hh - 0.6, fontSize: 16 });
		if (i < 2) line(s, L + 3.05, y + hh + 0.02, L + 3.05, y + hh + 0.16, T.mute, { arrow: true, w: 1.75 });
		y += hh + 0.18;
	});
	const h = 5.2, w = imgH("view_map_walk_04_clusters.png", h), im = { x: W - L - w, y: 1.3, w, h };
	img(s, "view_map_walk_04_clusters.png", im.x, im.y, w, h, { frame: T.line,
		alt: "SUMO-GUI capture with trusted cluster heads marked by black rings" });
	ring(s, im, 0.735, 0.425, 0.034);
	callout(s, im, "trusted forwarder", 0.62, 0.27, "n", [[0.722, 0.395]], 1.95);
	ring(s, im, 0.502, 0.505, 0.029);
	callout(s, im, "a group", 0.36, 0.62, "s", [[0.49, 0.53]], 1.15);
	txt(s, "Black rings: 20 trusted forwarders in this run, one per group.", { x: im.x, y: 6.58, w, h: 0.3,
		fontSize: 12, color: S.gray });
}

// ================================================================== 14 Verification
{
	const s = content("Alert Verification: Nobody Raises an Alarm Alone",
		"A single dishonest vehicle cannot start an alert: it needs three trusted witnesses among its five nearest " +
		"trusted neighbours. Their signatures are combined into one short certificate.");
	const st = [["1", "Accident alert created"], ["2", "The 5 nearest trusted neighbours are asked"],
		["3", "At least 3 of 5 confirm"], ["4", "Signatures combined into one 96-byte certificate"]];
	const w = 2.75, gap = 0.41;
	st.forEach(([n, t], i) => {
		const x = L + i * (w + gap);
		card(s, x, 1.3, w, 1.2, T.green, HEX.accent2);
		circleNum(s, n, x + 0.38, 1.9, 0.48, HEX.accent2, 16);
		txt(s, t, { x: x + 0.72, y: 1.36, w: w - 0.85, h: 1.08, fontSize: 16, valign: "middle" });
		if (i < 3) line(s, x + w + 0.04, 1.9, x + w + gap - 0.04, 1.9, T.mute, { arrow: true, w: 2 });
	});
	txt(s, "BLS12-381 aggregate signature [15]", { x: L + 3 * (w + gap), y: 2.56, w, h: 0.3,
		fontSize: 12, color: S.gray, align: "center" });
	const sz = 3.0;
	const a = { x: L + 0.3, y: 3.05, w: sz, h: sz }, b = { x: W - L - 0.3 - sz, y: 3.05, w: sz, h: sz };
	img(s, "sl_zoom_votes.png", a.x, a.y, sz, sz, { frame: T.line, alt: "Zoomed SUMO capture: confirmations arriving" });
	ring(s, a, 0.4, 0.51, 0.08); ring(s, a, 0.665, 0.51, 0.08);
	callout(s, a, "confirmations arriving", 0.53, 0.27, "n", [[0.43, 0.44], [0.64, 0.44]], 2.35);
	img(s, "sl_zoom_certificate.png", b.x, b.y, sz, sz, { frame: T.line, alt: "Zoomed SUMO capture: verified alert sent" });
	ring(s, b, 0.532, 0.51, 0.085);
	callout(s, b, "verified alert sent", 0.53, 0.25, "n", [[0.532, 0.43]], 2.05);
	txt(s, "Step 3: 2 of 5 confirmations in (+7 ms)", { x: a.x - 0.3, y: 6.15, w: sz + 0.6, h: 0.3, fontSize: 13,
		color: S.gray, align: "center" });
	txt(s, "Step 4: certificate made, alert sent (+12.5 ms)", { x: b.x - 0.4, y: 6.15, w: sz + 0.8, h: 0.3, fontSize: 13,
		color: S.gray, align: "center" });
	const mx = a.x + sz + 0.45, mw = b.x - 0.45 - mx;
	card(s, mx, 3.15, mw, 2.8, T.gray, T.line);
	const pts = [["No lone alarm: ", "a forger needs 3 trusted accomplices among the 5 nearest trusted vehicles."],
		["Small and fast: ", "one 96-byte certificate replaces five signatures; receivers check it once."]];
	pts.forEach(([k, v], i) => txt(s, [{ text: k, options: { bold: true, color: S.green } }, { text: v }],
		{ x: mx + 0.25, y: 3.35 + i * 1.25, w: mw - 0.5, h: 1.1, fontSize: 17 }));
}

// ================================================================== 15 Controlled forwarding
{
	const s = content("Controlled Forwarding and RSU Delivery",
		"Same crash, same traffic: 89 vehicles shouting versus 8 speaking. These two screenshots are one run each; " +
		"the averaged results are on slide 19.");
	txt(s, "Forward the alert only when a nearby vehicle or the RSU still needs it.", { x: L, y: 1.18, w: CW, h: 0.45,
		fontSize: 20, bold: true });
	const rules = [["Trusted forwarders go first", HEX.accent2], ["Others wait; farther vehicles go sooner", HEX.accent2],
		["Skip if every neighbour already has the alert", HEX.accent2], ["The RSU checks the alert and records it once", HEX.accent1]];
	rules.forEach(([t, hx], i) => {
		const y = 1.85 + i * 1.18;
		card(s, L + 0.25, y, 4.15, 0.98, hx === HEX.accent2 ? T.green : T.maroon, hx);
		circleNum(s, i + 1, L + 0.25, y + 0.49, 0.5, hx, 16);
		txt(s, t, { x: L + 0.62, y, w: 3.65, h: 0.98, fontSize: 17, valign: "middle" });
	});
	const w = 3.62, h = w * D.images["view_map_walk_07_flooding.png"][1] / D.images["view_map_walk_07_flooding.png"][0];
	const shots = [["Blind flooding", "view_map_walk_07_flooding.png", HEX.accent4, S.red, "89", "vehicles re-send",
		"3,380", "lost receptions"],
	["Proposed", "view_map_walk_09_duplicates.png", HEX.accent2, S.green, "8", "vehicles re-send", "78", "lost receptions"]];
	shots.forEach(([head, f, hx, col, n1, l1, n2, l2], i) => {
		const x = 5.2 + i * (w + 0.33);
		txt(s, head, { x, y: 1.78, w, h: 0.4, fontSize: 19, bold: true, color: col, align: "center" });
		img(s, f, x, 2.25, w, h, { frame: hx, fw: 2, alt: `${head}: SUMO-GUI capture of the same accident` });
		txt(s, [{ text: n1, options: { bold: true, fontSize: 24, color: col } }, { text: " " + l1, options: { breakLine: true } },
			{ text: n2, options: { bold: true, fontSize: 24, color: col } }, { text: " " + l2 }],
		{ x, y: 2.25 + h + 0.12, w, h: 0.95, fontSize: 15, align: "center" });
	});
	txt(s, "One run each (illustration). Orange rings: vehicles sending.", { x: L + 0.25, y: 6.62, w: 4.4, h: 0.3,
		fontSize: 12, color: S.gray });
}

// ================================================================== 16 Baselines
{
	const s = content("Four Baselines and the Proposed Method",
		"Pairing means every difference comes from the forwarding rule, not from luck in the traffic. The strongest " +
		"baseline, slotted 1-persistence with random delay, is the one we must beat.");
	const H = (t) => ({ text: t, options: { bold: true, color: S.white, fill: { color: C.accent1 } } });
	const rows = [[H("Approach"), H("How it forwards the alert")],
		["Blind flooding", "Every vehicle re-sends immediately"],
		["Flooding + random delay [1]", "Wait a short random time (0–5 ms), then re-send"],
		["Slotted 1-persistence [2]", "Farther vehicles go first; hearing a copy cancels yours"],
		[{ text: [{ text: "Slotted 1-p + random delay", options: { bold: true, breakLine: true } },
			{ text: "strongest baseline", options: { bold: true, color: S.blue, fontSize: 14 } }],
		options: { fill: { color: T.blue } } },
		{ text: "Distance slots plus a short random delay", options: { fill: { color: T.blue } } }],
		[{ text: "Proposed", options: { bold: true, color: S.green, fill: { color: T.green } } },
			{ text: "Trusted vehicles first; re-send only if a neighbour lacks the alert", options: { fill: { color: T.green } } }]];
	s.addTable(rows, { x: L, y: 1.35, w: CW, colW: [4.4, 7.833], rowH: [0.52, 0.62, 0.62, 0.62, 0.86, 0.66],
		fontSize: 18, color: S.ink, border: { type: "solid", pt: 0.75, color: T.line }, valign: "middle", margin: 7 });
	takeaway(s, 5.55, [{ text: "Fair test: ", options: { bold: true } },
		{ text: "all five run on identical traffic, crash and seed (paired runs) and share trust scores, alert " +
			"confirmation and RSU checks. Only the forwarding rule differs. Baselines are our implementations of the " +
			"published rules." }], 1.15, T.gray, T.line);
}

// ================================================================== 17 Algorithms
{
	const s = content("Algorithms Used and Our Improvements",
		"Every row is an existing published idea plus one specific change we made and measured.");
	const H = (t, fill) => ({ text: t, options: { bold: true, color: S.white, fill: { color: fill } } });
	const tech = (name, detail) => ({ text: [{ text: name, options: { bold: true, breakLine: true } },
		{ text: detail, options: { fontSize: 13, color: S.gray } }] });
	const ex = (t) => ({ text: t, options: { fill: { color: T.blue } } });
	const our = (t) => ({ text: t, options: { fill: { color: T.green } } });
	const rows = [[H("Technique", C.accent1), H("Existing method", C.accent3), H("Our improvement", C.accent2)],
		[tech("Trust score", "Beta model [13]: (good+1)/(good+bad+2)"), ex("Suppression trusts any sender [1, 2]"),
			our("Only vehicles with trust ≥ 0.7 lead and confirm")],
		[tech("Vehicle grouping", "DBSCAN [14]: 40 m radius, at least 3"), ex("Groups formed for network stability [9]"),
			our("Trusted cluster heads forward for their group")],
		[tech("Neighbour confirmation", "5 nearest trusted; 3 must agree"), ex("A signature proves only who sent it [6]"),
			our("No single vehicle can start an alert")],
		[tech("Combining signatures", "BLS12-381 [15]: one 96-byte certificate"), ex("Signatures verified in batches [6]"),
			our("One small certificate, checked once")],
		[tech("Controlled broadcast", "wait = tier × 25 ms + slot 0–20 ms + 0–5 ms"), ex("Farther first; a copy cancels [2]"),
			our("Trusted first; covered areas stay silent")],
		[tech("Trusted route to RSU", "shortest path over trusted forwarders"), ex("Route chosen by travel direction [10]"),
			our("A second, verified path to the RSU")]];
	s.addTable(rows, { x: L, y: 1.3, w: CW, colW: [4.0, 4.0, 4.233], rowH: [0.48, 0.8, 0.8, 0.8, 0.8, 0.8, 0.8],
		fontSize: 16, color: S.ink, border: { type: "solid", pt: 0.75, color: HEX.lt1 }, valign: "middle", margin: 6 });
}

// ================================================================== 18 Setup
sect("Evaluation");
{
	const s = content("Experimental Setup",
		"Every result is a mean over 30 paired runs with a 95 % confidence interval; a difference counts only if its " +
		"interval excludes zero.");
	const eq = [["6", "traffic densities", "50 to 500 vehicles"], ["30", "seeds per density", "different traffic each"],
		["180", "scenarios", "each with one crash"], ["5", "approaches", "on identical traffic (paired)"]];
	const ops = ["×", "=", "→"];
	eq.forEach(([n, a, b], i) => {
		const x = 0.565 + i * 3.2;
		card(s, x, 1.4, 2.6, 1.75, T.gray, T.line, { shadow: true });
		txt(s, n, { x, y: 1.45, w: 2.6, h: 0.75, fontSize: 40, bold: true, color: S.maroon, align: "center" });
		txt(s, a, { x, y: 2.2, w: 2.6, h: 0.4, fontSize: 17, bold: true, align: "center" });
		txt(s, b, { x, y: 2.6, w: 2.6, h: 0.4, fontSize: 14, color: S.gray, align: "center" });
		if (i < 3) txt(s, ops[i], { x: x + 2.6, y: 1.4, w: 0.6, h: 1.75, fontSize: 30, bold: true, color: S.gray,
			align: "center", valign: "middle" });
	});
	const env = ["SUMO 5×5 city grid [11]", "2 RSUs at junctions [16]", "10 % misbehaving vehicles", "802.11p radio, 300 m range [17]"];
	env.forEach((t, i) => s.addText(t, { shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06, x: L + i * 3.11,
		y: 3.45, w: 2.9, h: 0.55, fill: { color: HEX.lt1 }, line: { color: T.line, width: 1 }, fontSize: 15,
		color: S.ink, align: "center", valign: "middle", margin: 0 }));
	txt(s, "What we measure for each alert", { x: L, y: 4.3, w: CW, h: 0.42, fontSize: 20, bold: true, color: S.maroon });
	const met = [["Frames sent ↓", "messages sent per alert (overhead)"], ["Lost receptions ↓", "copies destroyed by collisions"],
		["Measured reach ↑", "share of vehicles reached"], ["Delay t90 ↓", "time until 90 % of vehicles have it"]];
	met.forEach(([h, b], i) => {
		const x = L + i * 3.11;
		card(s, x, 4.85, 2.9, 1.5, HEX.lt1, HEX.accent1);
		txt(s, h, { x: x + 0.15, y: 4.95, w: 2.6, h: 0.42, fontSize: 18, bold: true, color: S.maroon, align: "center" });
		txt(s, b, { x: x + 0.15, y: 5.42, w: 2.6, h: 0.8, fontSize: 15, align: "center" });
	});
	txt(s, "Statistics: mean ± 95 % confidence interval over 30 paired runs.", { x: L, y: 6.5, w: CW, h: 0.3,
		fontSize: 13, color: S.gray });
}

// ================================================================== 19 Results
{
	const s = content("Results and Performance Comparison (200 Vehicles)",
		"At 200 vehicles we are statistically tied with the strongest baseline on losses and reach, use slightly more " +
		"frames, and are slightly slower. Across densities: significantly fewer lost receptions at 250 to 500 vehicles, " +
		"higher reach at 50 and 100, and up to 9.4 ms slower at 500. The 100.0 % is a measured value from the simulator, " +
		"not a guarantee.");
	const order = ["flooding", "flooding_rad", "slotted1p", "slotted1p_rad", "proposed"];
	const name = { flooding: "Blind flooding", flooding_rad: "Flooding + random delay", slotted1p: "Slotted 1-p",
		slotted1p_rad: "Slotted 1-p + random delay", proposed: "Proposed" };
	const keys = [["transmissions", 1, Math.min], ["collision_losses", 0, Math.min], ["reachability", 1, Math.max],
		["t90_ms", 1, Math.min]];
	const best = {};
	keys.forEach(([k, dec, pick]) => { best[k] = pick(...order.map((p) => +A[p][k][0].toFixed(dec))); });
	const H = (t, al) => ({ text: t, options: { bold: true, color: S.white, fill: { color: C.accent1 }, align: al || "right" } });
	const rows = [[H("Approach", "left"), H("Frames sent ↓"), H("Lost receptions ↓"), H("Measured reach (%) ↑"),
		H("Delay t90 (ms) ↓")]];
	order.forEach((p) => {
		const fill = p === "slotted1p_rad" ? T.blue : p === "proposed" ? T.green : HEX.lt1;
		const strong = p === "slotted1p_rad" || p === "proposed";
		const row = [{ text: name[p], options: { bold: strong, color: p === "proposed" ? S.green : p === "slotted1p_rad" ? S.blue : S.ink,
			fill: { color: fill } } }];
		keys.forEach(([k, dec]) => {
			const [m, c] = A[p][k], mv = +m.toFixed(dec);
			row.push({ text: [{ text: fmt(mv, dec), options: { bold: mv === best[k] } },
				{ text: ` ±${fmt(+c.toFixed(dec), dec)}`, options: { fontSize: 12, color: S.gray } }],
			options: { align: "right", fill: { color: fill } } });
		});
		rows.push(row);
	});
	s.addTable(rows, { x: L, y: 1.22, w: CW, colW: [3.6, 2.05, 2.2, 2.35, 2.033], rowH: 0.37, fontSize: 16,
		color: S.ink, border: { type: "solid", pt: 0.5, color: T.line }, valign: "middle", margin: 4 });
	txt(s, "200 vehicles · mean ± 95 % CI over 30 paired runs · bold = best mean · blue = strongest baseline · green = proposed",
		{ x: L, y: 3.53, w: CW, h: 0.28, fontSize: 12, color: S.gray });
	const ser = [["Blind flooding", "flooding", "6B7280"], ["Slotted 1-p", "slotted1p", "8DB8E3"],
		["Slotted 1-p + random delay", "slotted1p_rad", HEX.accent3], ["Proposed", "proposed", HEX.accent2]];
	s.addChart(pres.charts.LINE, ser.map(([n, k]) => ({ name: n, labels: D.densities.map(String),
		values: D.frames_by_density[k].map((v) => +v.toFixed(1)) })), {
		x: L, y: 3.85, w: 5.85, h: 3.05, chartColors: ser.map((x) => x[2]), lineSize: 2.25, lineDataSymbol: "circle",
		lineDataSymbolSize: 6, valAxisLogScaleBase: 10, valAxisMinVal: 10, valAxisMaxVal: 1000,
		showTitle: true, title: "Frames per alert as traffic grows (log scale)", titleFontSize: 13, titleColor: HEX.dk1,
		titleFontFace: "+mn-lt", showLegend: true, legendPos: "b", legendFontSize: 11, legendFontFace: "+mn-lt",
		legendColor: HEX.dk1, catAxisLabelFontSize: 12, valAxisLabelFontSize: 12, catAxisLabelColor: HEX.accent6,
		valAxisLabelColor: HEX.accent6, catAxisLabelFontFace: "+mn-lt", valAxisLabelFontFace: "+mn-lt",
		showCatAxisTitle: true, catAxisTitle: "vehicles in the scenario", catAxisTitleFontSize: 12,
		catAxisTitleColor: HEX.accent6, catAxisTitleFontFace: "+mn-lt", valGridLine: { color: "E5E7EB", size: 0.75 },
		catGridLine: { style: "none" }, valAxisLabelFormatCode: "0" });
	const rx = 6.75, rw = W - L - rx;
	s.addText([{ text: "Trade-off: the proposed method is slightly slower", options: { bold: true, color: S.red, fontSize: 19,
		breakLine: true } },
	{ text: `Delay t90 ${fmt(A.proposed.t90_ms[0], 1)} vs ${fmt(A.slotted1p_rad.t90_ms[0], 1)} ms here (not significant); ` +
		`${M.NDTnSlotRadFiveH} ms at 500 vehicles (significant).` }],
	{ shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06, x: rx, y: 3.85, w: rw, h: 1.2, fill: { color: T.red },
		line: { color: HEX.accent4, width: 1.5 }, fontSize: 16, color: S.ink, valign: "middle", margin: [12, 12, 4, 4] });
	txt(s, [{ text: "✓ Fewest mean lost receptions: ", options: { bold: true, color: S.green } },
		{ text: `${fmt(Math.round(A.proposed.collision_losses[0]), 0)} vs ${fmt(Math.round(A.slotted1p_rad.collision_losses[0]), 0)} (not significant here)`,
			options: { breakLine: true } },
		{ text: "≈ Frames close to the strongest baseline: ", options: { bold: true, color: S.blue } },
		{ text: `${fmt(A.proposed.transmissions[0], 1)} vs ${fmt(A.slotted1p_rad.transmissions[0], 1)} (lines overlap)` }],
	{ x: rx + 0.05, y: 5.17, w: rw - 0.05, h: 0.85, fontSize: 15, paraSpaceAfter: 4 });
	s.addText([{ text: `Measured reach = ${M.NReachProp} % (30 paired runs under ideal radio model)`,
		options: { bold: true, breakLine: true } },
	{ text: "An experimental observation, not a guarantee of complete delivery." }],
	{ shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06, x: rx, y: 6.1, w: rw, h: 0.8, fill: { color: T.gray },
		line: { color: T.line, width: 1 }, fontSize: 14, color: S.ink, valign: "middle", margin: [12, 12, 3, 3] });
}

// ================================================================== 20 Security and limitations
{
	const s = content("Security Evaluation, Trade-offs and Limitations",
		"Persistent liars are stopped completely. Patient liars, honest 90 % of the time, are not: that is our first " +
		"future-work item. Sparse traffic and the simplified radio are stated openly.");
	txt(s, "Forged alerts recorded by an RSU (200 vehicles, 30 runs per bar)", { x: L, y: 1.2, w: 6.2, h: 0.35,
		fontSize: 15, bold: true });
	const bar = (x, title, labels, vals, axisTitle) => s.addChart(pres.charts.BAR, [{ name: "forged alerts recorded",
		labels, values: vals }], { x, y: 1.6, w: 3.05, h: 4.6, barDir: "col", chartColors: [HEX.accent4], barGapWidthPct: 55,
		showValue: true, dataLabelPosition: "outEnd", dataLabelFontSize: 14, dataLabelFontBold: true,
		dataLabelColor: HEX.dk1, dataLabelFontFace: "+mn-lt", dataLabelFormatCode: "0", valAxisMinVal: 0,
		valAxisMaxVal: 35, valAxisMajorUnit: 10, showLegend: false, showTitle: true, title, titleFontSize: 14,
		titleColor: HEX.dk1, titleFontFace: "+mn-lt", catAxisLabelFontSize: 12, valAxisLabelFontSize: 12,
		catAxisLabelColor: HEX.accent6, valAxisLabelColor: HEX.accent6, catAxisLabelFontFace: "+mn-lt",
		valAxisLabelFontFace: "+mn-lt", showCatAxisTitle: true, catAxisTitle: axisTitle, catAxisTitleFontSize: 12,
		catAxisTitleColor: HEX.accent6, catAxisTitleFontFace: "+mn-lt", valGridLine: { color: "E5E7EB", size: 0.75 },
		catGridLine: { style: "none" } });
	bar(L, "Persistent attackers", ["none", "no trust", "full"], D.forgery_persistent.map((x) => x[1]),
		"protection level");
	bar(L + 3.15, "On-off attackers", ["0 %", "50 %", "90 %"], D.forgery_onoff.map((x) => x[1]),
		"time honest (full protection)");
	txt(s, "Full protection = trust scores + 3-of-5 neighbour confirmation.", { x: L, y: 6.3, w: 6.2,
		h: 0.55, fontSize: 14, color: S.gray, italic: true });
	const rx = 6.95, rw = W - L - rx;
	s.addText([{ text: "What worked", options: { bold: true, color: S.green, fontSize: 19, breakLine: true } },
		{ text: `Persistent attackers stopped: with full protection, ${D.forgery_persistent[2][1]} of ` +
			`${D.forgery_persistent[2][0]} forged alerts were recorded.` }],
	{ shape: pres.shapes.ROUNDED_RECTANGLE, rectRadius: 0.06, x: rx, y: 1.25, w: rw, h: 1.3, fill: { color: T.green },
		line: { color: HEX.accent2, width: 1.25 }, fontSize: 16, color: S.ink, valign: "middle", margin: [12, 12, 4, 4] });
	card(s, rx, 2.72, rw, 4.15, T.red, HEX.accent4, { lw: 1.25 });
	txt(s, "What did not work, and limits", { x: rx + 0.2, y: 2.82, w: rw - 0.4, h: 0.42, fontSize: 19, bold: true,
		color: S.red });
	const lim = [["On-off attackers: ", `vehicles honest 90 % of the time still earn trust: ${D.forgery_onoff[2][1]} of ` +
		`${D.forgery_onoff[2][0]} forged alerts recorded.`],
	["Delay cost: ", `confirming every alert adds about ${M.NSecTn} ms of delay.`],
	["Sparse traffic: ", "too few trusted neighbours, so no alert released in 14 of 30 runs (50 vehicles, 150 m range)."],
	["Simulation only: ", "ideal radio (no fading or obstacles); keys from vehicle IDs, no public-key infrastructure."]];
	const limRuns = [];
	lim.forEach(([k, v], i) => limRuns.push({ text: k, options: { bold: true } },
		{ text: v, options: { breakLine: i < lim.length - 1 } }));
	txt(s, limRuns, { x: rx + 0.2, y: 3.4, w: rw - 0.4, h: 3.35, fontSize: 17, paraSpaceAfter: 14 });
}

// ================================================================== 21 Conclusion
sect("Conclusion");
{
	const s = content("Conclusion and Future Scope",
		"Trusted, controlled forwarding tames the broadcast storm. It costs milliseconds, and it is only as strong as " +
		"the trust score.");
	const bullets = (arr) => arr.map((t, i) => ({ text: t, options: { bullet: { indent: 18 }, breakLine: i < arr.length - 1 } }));
	card(s, L, 1.25, 6.0, 3.3, T.green, HEX.accent2);
	txt(s, "What we showed", { x: L + 0.25, y: 1.35, w: 5.5, h: 0.42, fontSize: 20, bold: true, color: S.green });
	txt(s, bullets(["A complete, working pipeline: city traffic → alert recorded at an RSU",
		`${M.NCutVsFlood} % fewer frames than blind flooding at 200 vehicles, similar measured reach`,
		"Fewer lost receptions in dense traffic and higher reach in sparse traffic than the strongest baseline"]),
	{ x: L + 0.25, y: 1.85, w: 5.5, h: 2.6, fontSize: 17, paraSpaceAfter: 8 });
	const rx = L + 6.233;
	card(s, rx, 1.25, 6.0, 3.3, T.blue, HEX.accent3);
	txt(s, "Future scope", { x: rx + 0.25, y: 1.35, w: 5.5, h: 0.42, fontSize: 20, bold: true, color: S.blue });
	txt(s, bullets(["Trust that resists on-off attackers; a real key system (PKI)",
		"Realistic radio (fading) and real road maps", "A fallback when too few trusted neighbours exist",
		"Cloud integration: proposed, not yet implemented"]),
	{ x: rx + 0.25, y: 1.85, w: 5.5, h: 2.6, fontSize: 17, paraSpaceAfter: 8 });
	const tiles = [[`${M.NCutVsFlood} %`, "fewer frames than blind flooding (200 vehicles)", true],
		[`${D.forgery_persistent[2][1]} of ${D.forgery_persistent[2][0]}`, "forged alerts recorded (persistent attackers)", true],
		[`${M.NDTnSlotRadFiveH} ms`, "delay vs strongest baseline (500 vehicles)", false],
		[`${D.forgery_onoff[2][1]} of ${D.forgery_onoff[2][0]}`, "forged alerts recorded (on-off attackers)", false]];
	tiles.forEach(([v, lab, good], i) => {
		const x = L + i * 3.11;
		card(s, x, 4.72, 2.9, 1.05, good ? T.green : T.red, good ? HEX.accent2 : HEX.accent4);
		txt(s, v, { x: x + 0.15, y: 4.76, w: 2.6, h: 0.5, fontSize: 24, bold: true, color: good ? S.green : S.red });
		txt(s, lab, { x: x + 0.15, y: 5.24, w: 2.65, h: 0.5, fontSize: 13 });
	});
	takeaway(s, 5.95, [{ text: "Conclusion: ", options: { bold: true } },
		{ text: "trusted, controlled forwarding greatly reduces the broadcast storm; it costs a few milliseconds, and its " +
			"security is only as strong as the trust score." }], 0.92);
}

// ================================================================== 22 Deliverables
{
	const s = content("Project Deliverables and TEA",
		"The manuscript is prepared, not submitted or accepted: we are not claiming publication.");
	txt(s, "TEA: Technical Enrichment Activities", { x: L, y: 1.17, w: CW, h: 0.32, fontSize: 14, color: S.gray });
	const q = [
		["TEA 1 · Online course", "Completed: 5 of 5 members", S.green, [{ text: "Introduction to the Internet of Things and " +
			"Embedded Systems", options: { italic: true } }, { text: " (UC Irvine, Coursera); all five certificates verified" }]],
		["TEA 2 · Research paper", "Prepared as a manuscript", S.amber, [{ text: "Trust-Aware Cluster-Based Broadcast " +
			"Suppression for Real-Time Vehicular Emergency Alerts. ", options: { italic: true } },
		{ text: "Not yet published or accepted.", options: { bold: true } }]],
		["TEA 3 · Documentation website", "Completed and deployed", S.green,
			[{ text: "iov-documentation-portal.vercel.app", options: { fontFace: "Courier New" } }]],
		["Source code and report", "Available", S.green, [{ text: "github.com/AkhilRudrapaka/",
			options: { fontFace: "Courier New", breakLine: true } }, { text: "IoV-Emergency-Broadcast",
			options: { fontFace: "Courier New", breakLine: true } }, { text: "Project Implementation Report" }]]];
	q.forEach(([h, st, col, body], i) => {
		const x = L + (i % 2) * 6.233, y = 1.6 + Math.floor(i / 2) * 2.65;
		card(s, x, y, 6.0, 2.4, T.gray, T.line, { shadow: true });
		txt(s, h, { x: x + 0.25, y: y + 0.18, w: 5.5, h: 0.42, fontSize: 20, bold: true, color: S.maroon });
		txt(s, st, { x: x + 0.25, y: y + 0.62, w: 5.5, h: 0.36, fontSize: 16, bold: true, color: col });
		txt(s, body, { x: x + 0.25, y: y + 1.05, w: 5.5, h: 1.25, fontSize: 16 });
	});
}

// ================================================================== 23-24 References
sect("References");
[[0, 10, "References (1 of 2)"], [10, 19, "References (2 of 2)"]].forEach(([a, b, t]) => {
	const s = content(t, "");
	const runs = [];
	REFS.slice(a, b).forEach((r, i) => runs.push({ text: `[${a + i + 1}]  ${r}`,
		options: { breakLine: a + i + 1 < b, paraSpaceAfter: 5 } }));
	txt(s, runs, { x: L, y: 1.25, w: CW, h: 5.7, fontSize: 14, color: S.ink });
});

// ================================================================== 25 Thank you
{
	slideNo += 1;
	const s = pres.addSlide({ masterName: "CLOSING", sectionTitle: section });
	s.addNotes("Thank the panel and invite questions.");
	card(s, (W - 3.4) / 2, 0.7, 3.4, 1.1, HEX.lt1, undefined, { r: 0.1 });
	const lw = 2.9;
	img(s, "../logo.png", (W - lw) / 2, 0.82, lw, lw * 568 / 1948, { alt: "Amrita Vishwa Vidyapeetham logo" });
	txt(s, "Thank You", { x: 1, y: 2.2, w: W - 2, h: 1.2, fontSize: 60, bold: true, color: S.white, align: "center",
		valign: "middle", fontFace: THEME.headFontFace });
	txt(s, "Questions and Viva Voce", { x: 1, y: 3.4, w: W - 2, h: 0.55, fontSize: 26, color: S.white, align: "center" });
	txt(s, "Emergency Message Dissemination for Broadcast Storm Mitigation in the Internet of Vehicles",
		{ x: 1.2, y: 4.45, w: W - 2.4, h: 0.9, fontSize: 20, bold: true, color: S.white, align: "center", valign: "middle" });
	txt(s, "Team 83   |   Guide: Dr. Radhika G   |   Department of CSE, Amrita Vishwa Vidyapeetham",
		{ x: 1, y: 5.55, w: W - 2, h: 0.45, fontSize: 17, color: S.white, align: "center" });
}

(async () => {
	await pres.writeFile({ fileName: OUT });
	await applyTheme(OUT, THEME);
	console.log("slides:", slideNo, "->", OUT);
})().catch((e) => { console.error(e); process.exit(1); });
