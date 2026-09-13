// Included only in the pinned stock ChatWidget test module; no production patches.
mod ithilien_ui {
    use super::*;
    use codex_protocol::openai_models::ReasoningEffort;
    use ratatui::buffer::Buffer;
    use ratatui::layout::Rect;

    #[tokio::test]
    async fn ithilien_stock_ui_cells() {
        let rgb = |name: &str| -> (u8, u8, u8) {
            serde_json::from_str(&std::env::var(name).unwrap()).unwrap()
        };
        let colors = crate::terminal_probe::DefaultColors {
            fg: rgb("ITHILIEN_UI_FG"),
            bg: rgb("ITHILIEN_UI_BG"),
        };
        let mut records = Vec::new();
        for width in [60, 100] {
            for (mode, effort) in [
                ("low", ReasoningEffort::Low),
                ("max", ReasoningEffort::Max),
                ("ultra", ReasoningEffort::Ultra),
            ] {
                let (mut chat, _rx, _op_rx) = make_chatwidget_manual(None).await;
                chat.bottom_pane
                    .set_placeholder_text("Ask Codex to do anything".into());
                chat.bottom_pane
                    .set_active_reasoning_effort_baseline(Some(&ReasoningEffort::Low));
                chat.on_task_started();
                let start = std::time::Instant::now();
                for phase in 0..8 {
                    let record = crate::terminal_palette::with_test_default_colors(colors, || {
                        if phase == 0 {
                            chat.bottom_pane.set_active_reasoning_effort(Some(&effort));
                        }
                        let height = chat.bottom_pane.desired_height(width);
                        let area = Rect::new(0, 0, width, height);
                        let mut buffer = Buffer::empty(area);
                        chat.bottom_pane.render(area, &mut buffer);
                        let cells: Vec<_> = buffer.content().iter().enumerate().map(|(i, c)| {
                            serde_json::json!({"row": i / width as usize, "col": i % width as usize,
                                "text": c.symbol(), "fg": format!("{:?}", c.fg),
                                "bg": format!("{:?}", c.bg), "modifiers": format!("{:?}", c.modifier)})
                        }).collect();
                        serde_json::json!({"file": format!("{mode}-{phase}"), "kind": "stock-ui",
                            "level": "native", "width": width, "height": height,
                            "mode": mode, "phase": phase, "elapsed_ms": start.elapsed().as_millis(),
                            "cells": cells})
                    });
                    records.push(record);
                    if phase < 7 {
                        tokio::time::sleep(std::time::Duration::from_millis(300)).await;
                    }
                }
            }
        }
        std::fs::write(
            std::env::var("ITHILIEN_UI_OUTPUT").unwrap(),
            serde_json::to_string_pretty(&records).unwrap(),
        )
        .unwrap();
    }
}
