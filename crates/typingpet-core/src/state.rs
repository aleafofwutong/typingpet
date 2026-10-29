//! 应用状态机：待机、普通输入、组合键反应与低频待机彩蛋。
//!
//! 这一层刻意不依赖任何 GUI/输入实现，便于 headless 全链路验证。

use crate::keys::{KeyReactionStore, KeyStroke};
use crate::picker::{ImagePicker, Rng};
use std::path::PathBuf;

pub const IDLE_DELAY: f64 = 0.75;
pub const SURPRISE_DURATION: f64 = 10.0;
pub const SURPRISE_CHECK_INTERVAL: f64 = 10.0;
const SURPRISE_CHANCE_DENOMINATOR: usize = 10;
const SURPRISE_CHANCE_SUCCESSES: usize = 3;

#[derive(Debug, Clone, PartialEq)]
pub enum Action {
    /// 显示某张图片
    ShowImage(PathBuf),
    /// 播放弹跳动画，参数为振幅（像素）
    Bounce(f64),
}

#[derive(Debug)]
pub struct PetState {
    idle_url: Option<PathBuf>,
    typing_url: Option<PathBuf>,
    reaction_urls: Vec<PathBuf>,
    surprise_url: Option<PathBuf>,
    current_image: Option<PathBuf>,
    idle_deadline: Option<f64>,
    surprise_deadline: Option<f64>,
    next_surprise_at: Option<f64>,
    shake_amplitude: f64,
    reaction_count: usize,
}

impl PetState {
    pub fn new(
        idle_url: Option<PathBuf>,
        typing_url: Option<PathBuf>,
        reaction_urls: Vec<PathBuf>,
        surprise_url: Option<PathBuf>,
        shake_amplitude: f64,
    ) -> Self {
        Self {
            reaction_count: reaction_urls.len(),
            idle_url,
            typing_url,
            reaction_urls,
            surprise_url,
            current_image: None,
            idle_deadline: None,
            surprise_deadline: None,
            next_surprise_at: None,
            shake_amplitude,
        }
    }

    pub fn update_sources(
        &mut self,
        idle_url: Option<PathBuf>,
        typing_url: Option<PathBuf>,
        reaction_urls: Vec<PathBuf>,
        surprise_url: Option<PathBuf>,
        shake_amplitude: f64,
    ) {
        self.reaction_count = reaction_urls.len();
        self.idle_url = idle_url;
        self.typing_url = typing_url;
        self.reaction_urls = reaction_urls;
        self.surprise_url = surprise_url;
        self.shake_amplitude = shake_amplitude;
        self.current_image = None;
        self.idle_deadline = None;
        self.surprise_deadline = None;
        self.next_surprise_at = None;
    }

    pub fn current_image(&self) -> Option<&PathBuf> {
        self.current_image.as_ref()
    }

    pub fn reaction_count(&self) -> usize {
        self.reaction_count
    }

    pub fn is_showing_idle(&self) -> bool {
        match (&self.current_image, &self.idle_url) {
            (Some(current), Some(idle)) => current == idle,
            (None, _) => true,
            _ => false,
        }
    }

    /// 待机图 URL（用于启动时显示）。
    pub fn idle_url(&self) -> Option<&PathBuf> {
        self.idle_url.as_ref()
    }

    /// 首次显示：返回待机图动作。
    pub fn initial_actions(&mut self) -> Vec<Action> {
        let mut actions = Vec::new();
        if let Some(idle) = self.idle_url.clone() {
            self.current_image = Some(idle.clone());
            actions.push(Action::ShowImage(idle));
        }
        actions
    }

    /// 键输入处理。`stroke` 为 `None` 时表示"测试按钮"（跳过精确规则匹配）。
    pub fn on_key(
        &mut self,
        stroke: Option<KeyStroke>,
        rules: &KeyReactionStore,
        rng: &mut impl Rng,
        now: f64,
    ) -> Vec<Action> {
        let (chosen, should_bounce) = match stroke {
            // 按住 Ctrl/Alt/Shift/Super 的组合键才使用 9->1...6。
            Some(stroke) if stroke.modifiers != crate::keys::KeyModifiers::NONE => (
                rules.image_path(stroke).or_else(|| self.pick_random(rng)),
                true,
            ),
            // BuiltIn 的普通按键固定使用输入动画；自定义图库没有该动画时
            // 仍兼容原有的精确规则/随机反应行为。
            Some(stroke) => (
                self.typing_url
                    .clone()
                    .or_else(|| rules.image_path(stroke))
                    .or_else(|| self.pick_random(rng)),
                false,
            ),
            None => (self.pick_random(rng), true),
        };

        let Some(chosen) = chosen else {
            return Vec::new();
        };

        self.idle_deadline = Some(now + IDLE_DELAY);
        self.surprise_deadline = None;
        self.next_surprise_at = self
            .surprise_url
            .as_ref()
            .map(|_| now + SURPRISE_CHECK_INTERVAL);

        // 连续普通输入时保持 APNG 自然循环，只刷新停止输入的截止时间。
        if self.current_image.as_ref() == Some(&chosen) {
            return Vec::new();
        }

        let mut actions = Vec::new();
        self.current_image = Some(chosen.clone());
        actions.push(Action::ShowImage(chosen));
        if should_bounce && self.shake_amplitude > 0.0 {
            actions.push(Action::Bounce(self.shake_amplitude));
        }
        actions
    }

    /// 定时推进：停止输入后回待机，并在长时间待机时偶尔播放 10 秒彩蛋。
    pub fn tick(&mut self, now: f64, rng: &mut impl Rng) -> Vec<Action> {
        if let Some(deadline) = self.idle_deadline {
            if now < deadline {
                return Vec::new();
            }
            self.idle_deadline = None;
            self.surprise_deadline = None;
            return self.show_idle();
        }

        if let Some(deadline) = self.surprise_deadline {
            if now < deadline {
                return Vec::new();
            }
            self.surprise_deadline = None;
            self.schedule_surprise(now);
            return self.show_idle();
        }

        if self.surprise_url.is_none() || !self.is_showing_idle() {
            return Vec::new();
        }
        if self.next_surprise_at.is_none() {
            self.schedule_surprise(now);
            return Vec::new();
        }
        if now < self.next_surprise_at.unwrap_or(f64::INFINITY) {
            return Vec::new();
        }

        if rng.index(SURPRISE_CHANCE_DENOMINATOR) >= SURPRISE_CHANCE_SUCCESSES {
            self.schedule_surprise(now);
            return Vec::new();
        }

        self.next_surprise_at = None;
        self.surprise_deadline = Some(now + SURPRISE_DURATION);
        let surprise = self.surprise_url.clone().expect("checked above");
        self.current_image = Some(surprise.clone());
        vec![Action::ShowImage(surprise)]
    }

    fn show_idle(&mut self) -> Vec<Action> {
        let Some(idle) = self.idle_url.clone() else {
            return Vec::new();
        };
        if self.current_image.as_ref() == Some(&idle) {
            return Vec::new();
        }
        self.current_image = Some(idle.clone());
        vec![Action::ShowImage(idle)]
    }

    fn schedule_surprise(&mut self, now: f64) {
        self.next_surprise_at = self
            .surprise_url
            .as_ref()
            .map(|_| now + SURPRISE_CHECK_INTERVAL);
    }

    fn pick_random(&self, rng: &mut impl Rng) -> Option<PathBuf> {
        let names: Vec<String> = self
            .reaction_urls
            .iter()
            .map(|path| path.to_string_lossy().to_string())
            .collect();
        let picker = ImagePicker::new(names);
        let current_key = self
            .current_image
            .as_ref()
            .map(|path| path.to_string_lossy().to_string());
        picker
            .next_excluding(current_key.as_deref(), rng)
            .map(PathBuf::from)
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::picker::FixedRng;

    fn state() -> PetState {
        PetState::new(
            Some(PathBuf::from("/img/pet-idle.png")),
            Some(PathBuf::from("/img/pet-typing.apng")),
            vec![
                PathBuf::from("/img/pet-left.png"),
                PathBuf::from("/img/pet-right.png"),
                PathBuf::from("/img/pet-question.png"),
            ],
            Some(PathBuf::from("/img/pet-surprise.gif")),
            9.0,
        )
    }

    #[test]
    fn initial_actions_show_idle_image() {
        let mut state = state();
        assert_eq!(
            state.initial_actions(),
            vec![Action::ShowImage(PathBuf::from("/img/pet-idle.png"))]
        );
        assert!(state.is_showing_idle());
    }

    #[test]
    fn keypress_shows_reaction_then_returns_to_idle() {
        let mut state = state();
        state.initial_actions();
        let rules = KeyReactionStore::new("/nonexistent-rules");
        let mut rng = FixedRng(0);

        let actions = state.on_key(None, &rules, &mut rng, 100.0);
        assert_eq!(actions.len(), 2);
        assert!(matches!(actions[0], Action::ShowImage(_)));
        assert_eq!(actions[1], Action::Bounce(9.0));
        assert!(!state.is_showing_idle());

        // 0.75s 之前不回待机
        assert!(state.tick(100.7, &mut rng).is_empty());
        // 到点后回待机
        assert_eq!(
            state.tick(100.76, &mut rng),
            vec![Action::ShowImage(PathBuf::from("/img/pet-idle.png"))]
        );
        assert!(state.is_showing_idle());
        // 已回待机后不再重复
        assert!(state.tick(101.0, &mut rng).is_empty());
    }

    #[test]
    fn plain_key_uses_typing_animation_without_restarting_it() {
        let mut state = state();
        state.initial_actions();
        let rules = KeyReactionStore::new("/nonexistent-rules");
        let mut rng = FixedRng(0);
        let plain = KeyStroke::new(30, crate::keys::KeyModifiers::NONE);

        assert_eq!(
            state.on_key(Some(plain), &rules, &mut rng, 10.0),
            vec![Action::ShowImage(PathBuf::from("/img/pet-typing.apng"))]
        );
        assert!(state.on_key(Some(plain), &rules, &mut rng, 10.1).is_empty());
        assert!((state.next_surprise_at.unwrap_or_default() - 20.1).abs() < f64::EPSILON);
        assert!(state.tick(10.8, &mut rng).is_empty());
        assert_eq!(
            state.tick(10.86, &mut rng),
            vec![Action::ShowImage(PathBuf::from("/img/pet-idle.png"))]
        );
        assert!((state.next_surprise_at.unwrap_or_default() - 20.1).abs() < f64::EPSILON);
    }

    #[test]
    fn idle_surprise_starts_after_random_delay_and_lasts_ten_seconds() {
        let mut state = state();
        state.initial_actions();
        let mut rng = FixedRng(0);

        assert!(state.tick(0.0, &mut rng).is_empty());
        assert!(state.tick(9.9, &mut rng).is_empty());
        assert_eq!(
            state.tick(10.0, &mut rng),
            vec![Action::ShowImage(PathBuf::from("/img/pet-surprise.gif"))]
        );
        assert!(state.tick(19.99, &mut rng).is_empty());
        assert_eq!(
            state.tick(20.0, &mut rng),
            vec![Action::ShowImage(PathBuf::from("/img/pet-idle.png"))]
        );
    }

    #[test]
    fn failed_surprise_roll_schedules_another_random_check() {
        let mut state = state();
        state.initial_actions();
        let mut rng = FixedRng(3);

        assert!(state.tick(0.0, &mut rng).is_empty());
        assert_eq!(state.next_surprise_at, Some(10.0));
        assert!(state.tick(10.0, &mut rng).is_empty());
        assert!(state.is_showing_idle());
        assert_eq!(state.next_surprise_at, Some(20.0));
    }

    #[test]
    fn reaction_never_repeats_the_image_shown_right_before() {
        let mut state = state();
        state.initial_actions();
        let rules = KeyReactionStore::new("/nonexistent-rules");
        let mut rng = FixedRng(0);
        let mut previous = state.current_image().cloned();

        for _ in 0..50 {
            let actions = state.on_key(None, &rules, &mut rng, 200.0);
            let shown = match actions.first() {
                Some(Action::ShowImage(path)) => path.clone(),
                _ => panic!("expected ShowImage"),
            };
            assert_ne!(Some(shown.clone()), previous, "连续两次显示了同一张反应图");
            previous = Some(shown);
        }
    }

    #[test]
    fn exact_rule_wins_over_random_reaction() {
        let root = std::env::temp_dir().join(format!("typingpet-state-{}", crate::unique_id()));
        let source = root.join("special.png");
        std::fs::create_dir_all(&root).expect("mkdir");
        std::fs::write(&source, b"\x89PNG\r\n\x1a\n").expect("write");

        let store_dir = root.join("rules");
        let mut store = KeyReactionStore::new(&store_dir);
        let modifiers = crate::keys::KeyModifiers::empty().with(crate::keys::KeyModifiers::CONTROL);
        let stroke = KeyStroke::new(37, modifiers);
        store.set_rule(stroke, &source).expect("set rule");
        let expected = store.image_path(stroke).expect("rule image");

        let mut state = state();
        state.initial_actions();
        let mut rng = FixedRng(0);
        let actions = state.on_key(Some(stroke), &store, &mut rng, 0.0);
        assert_eq!(actions[0], Action::ShowImage(expected));

        // 未注册的按键走随机反应
        let other = KeyStroke::new(38, modifiers);
        let actions = state.on_key(Some(other), &store, &mut rng, 0.0);
        assert!(matches!(actions.first(), Some(Action::ShowImage(_))));

        std::fs::remove_dir_all(&root).ok();
    }

    #[test]
    fn zero_shake_level_skips_bounce() {
        let mut state = PetState::new(
            Some(PathBuf::from("/img/pet-idle.png")),
            None,
            vec![PathBuf::from("/img/a.png")],
            None,
            0.0,
        );
        state.initial_actions();
        let rules = KeyReactionStore::new("/nonexistent-rules");
        let mut rng = FixedRng(0);
        let actions = state.on_key(None, &rules, &mut rng, 0.0);
        assert_eq!(actions.len(), 1);
    }
}
