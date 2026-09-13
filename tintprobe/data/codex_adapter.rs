// Included as a child of the pinned upstream diff_render module for evaluation.
#[cfg(test)]
mod ithilien_evaluation {
    use super::*;
    #[test]
    fn exported_theme_native_cells() {
        let root = PathBuf::from(std::env::var("ITHILIEN_ROOT").unwrap());
        let output = PathBuf::from(std::env::var("ITHILIEN_CODEX_OUTPUT").unwrap());
        let mut reader = std::io::BufReader::new(std::fs::File::open(PathBuf::from(std::env::var("ITHILIEN_CODEX_THEME").unwrap())).unwrap());
        let theme = syntect::highlighting::ThemeSet::load_from_reader(&mut reader).unwrap();
        crate::render::highlight::set_syntax_theme(theme);
        let scopes = diff_scope_background_rgbs();
        assert!(scopes.inserted.is_some() && scopes.deleted.is_some(), "Exported theme diff scopes were not loaded");
        let mut records = Vec::new();
        for (file, lang) in [("codex/rust.after.rs", "rust"), ("codex/py.after.py", "python"), ("python/python-models.after.py", "python"), ("python/python-async.after.py", "python"), ("python/python-expressions.after.py", "python")] {
            let code = std::fs::read_to_string(std::path::PathBuf::from(std::env::var("TINTPROBE_FIXTURES").unwrap()).join(file)).unwrap();
            let syntax = highlight_code_to_styled_spans(&code, lang).unwrap();
            for (level_name, level) in [("truecolor", DiffColorLevel::TrueColor), ("ansi256", DiffColorLevel::Ansi256), ("ansi16", DiffColorLevel::Ansi16)] {
                for (kind_name, kind) in [("insert", DiffLineType::Insert), ("delete", DiffLineType::Delete)] {
                    for width in [40, 80] {
                        let backgrounds = resolve_diff_backgrounds_for(DiffTheme::Light, level, diff_scope_background_rgbs());
                        let mut lines = Vec::new();
                        for (i, text) in code.lines().enumerate() {
                            lines.extend(push_wrapped_diff_line_inner_with_theme_and_color_level(i+1, kind, text, width, 2, syntax.get(i).map(Vec::as_slice), DiffTheme::Light, level, backgrounds));
                        }
                        let height = lines.len() as u16;
                        let area = Rect::new(0,0,width as u16,height);
                        let mut buffer = Buffer::empty(area);
                        use ratatui::widgets::Widget;
                        Paragraph::new(lines).render(area,&mut buffer);
                        let cells: Vec<_> = buffer.content().iter().enumerate().map(|(i,c)| serde_json::json!({"row":i/width,"col":i%width,"text":c.symbol(),"fg":format!("{:?}",c.fg),"bg":format!("{:?}",c.bg),"modifiers":format!("{:?}",c.modifier)})).collect();
                        records.push(serde_json::json!({"file":file,"level":level_name,"kind":kind_name,"width":width,"cells":cells}));
                    }
                }
            }
        }
        std::fs::write(output,serde_json::to_string_pretty(&records).unwrap()).unwrap();
    }
}
