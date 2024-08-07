use std::{
    fs, io,
    path::{Path, PathBuf},
};

use color_eyre::eyre::{Context, Result};
use rand::Rng;

/// Represents a newly created directory and optionally acts as a RAII guard that (attempts to)
/// delete the directory and anything in it when dropped.
#[derive(Debug)]
pub struct Dir {
    /// path to created directory
    path: PathBuf,

    /// drop flag, if this is `true` when [`Dir`] is dropped then the drop hook will call
    /// [`fs::remove_dir_all()`] on `path`, if this fails it will log a warning but take no other
    /// action.
    pub drop: bool,
}

impl Dir {
    /// Attempts to create a new directory at `path`.
    ///
    /// By default directories created this way **are not** deleted when [`Dir`] is dropped.
    #[inline]
    pub fn new(path: PathBuf) -> Result<Self> {
        fs::create_dir(&path).wrap_err("Failed to create named directory")?;
        Ok(Self { path, drop: false })
    }

    /// Attempts to create a new tempoerary directory
    ///
    /// The directory is created in the path retunred by [`std::env::temp_dir()`] and is named
    /// `probe-XXXXXXXX` where `X` is a random alphanumeric digit. Will try again (indefinitely) if
    /// directory creation errors with [`AlreadyExists`](io::ErrorKind::AlreadyExists).
    ///
    /// By default directories created this way **are** deleted when [`Dir`] is dropped.
    pub fn temp(drop: bool) -> Result<Self> {
        fn rand_alphanumeric(len: usize) -> String {
            const CHARSET: &[u8] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ\
                                    abcdefghijklmnopqrstuvwxyz\
                                    0123456789";

            let mut rng = rand::thread_rng();

            (0..len)
                .map(|_| {
                    let idx = rng.gen_range(0..CHARSET.len());
                    CHARSET[idx] as char
                })
                .collect()
        }

        let mut path = std::env::temp_dir();
        path.push(format!("probe-{}", rand_alphanumeric(8)));

        match fs::create_dir(&path) {
            Ok(_) => Ok(Self { path, drop }),
            Err(e) => match e.kind() {
                io::ErrorKind::AlreadyExists => Self::temp(drop),
                _ => Err(e).wrap_err("Failed to create temp directory"),
            },
        }
    }

    #[inline]
    pub fn path(&self) -> &Path {
        self.path.as_path()
    }
}

impl AsRef<Path> for Dir {
    fn as_ref(&self) -> &Path {
        self.path.as_path()
    }
}

impl Drop for Dir {
    fn drop(&mut self) {
        if self.drop {
            if let Err(e) = fs::remove_dir_all(&self.path) {
                log::warn!(
                    "Failed to remove temporary directory '{}' because: {}",
                    self.path.to_string_lossy(),
                    e
                );
            }
        }
    }
}

pub(crate) fn sig_to_name(sig: i32) -> Option<&'static str> {
    Some(match sig {
        libc::SIGHUP => "SIGHUP",
        libc::SIGINT => "SIGINT",
        libc::SIGQUIT => "SIGQUIT",
        libc::SIGILL => "SIGILL",
        libc::SIGTRAP => "SIGTRAP",
        libc::SIGABRT => "SIGABRT/SIGIOT", // SIGABRT and SIGIOT have the same code
        libc::SIGBUS => "SIGBUS",
        libc::SIGFPE => "SIGFPE",
        libc::SIGKILL => "SIGKILL",
        libc::SIGUSR1 => "SIGUSR1",
        libc::SIGSEGV => "SIGSEGV",
        libc::SIGUSR2 => "SIGUSR2",
        libc::SIGPIPE => "SIGPIPE",
        libc::SIGALRM => "SIGALRM",
        libc::SIGTERM => "SIGTERM",
        libc::SIGSTKFLT => "SIGSTKFLT",
        libc::SIGCHLD => "SIGCHLD",
        libc::SIGCONT => "SIGCONT",
        libc::SIGSTOP => "SIGSTOP",
        libc::SIGTSTP => "SIGTSTP",
        libc::SIGTTIN => "SIGTTIN",
        libc::SIGTTOU => "SIGTTOU",
        libc::SIGURG => "SIGURG",
        libc::SIGXCPU => "SIGXCPU",
        libc::SIGXFSZ => "SIGXFSZ",
        libc::SIGVTALRM => "SIGVTALRM",
        libc::SIGPROF => "SIGPROF",
        libc::SIGWINCH => "SIGWINCH",
        libc::SIGIO => "SIGIO/SIGPOLL", // SIGIO and SIGPOLL have the same code
        libc::SIGPWR => "SIGPWR",
        libc::SIGSYS => "SIGSYS",

        _ => return None,
    })
}

#[test]
fn sig_eq() {
    assert_eq!(libc::SIGABRT, libc::SIGIOT);
    assert_eq!(libc::SIGIO, libc::SIGPOLL);
}
