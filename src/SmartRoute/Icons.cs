using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Drawing.Imaging;
using System.IO;

namespace SmartRoute
{
    /// <summary>Generates simple toolbar icons at run time (no image files to ship).</summary>
    public static class Icons
    {
        static readonly int[] Sizes = { 20, 32, 40, 64, 96, 128 };

        static void Draw(Graphics g, int x, int size, string letter, Color color)
        {
            g.SmoothingMode = SmoothingMode.AntiAlias;
            using (var b = new SolidBrush(color))
                g.FillEllipse(b, x + 1, 1, size - 2, size - 2);
            using (var f = new Font("Segoe UI", size * 0.46f, FontStyle.Bold, GraphicsUnit.Pixel))
            using (var sf = new StringFormat { Alignment = StringAlignment.Center, LineAlignment = StringAlignment.Center })
                g.DrawString(letter, f, Brushes.White, new RectangleF(x, 0, size, size), sf);
        }

        /// <summary>One strip (all icons side by side) per size.</summary>
        public static string[] Strips(string dir, string[] letters, Color[] colors)
        {
            Directory.CreateDirectory(dir);
            var paths = new string[Sizes.Length];
            for (int s = 0; s < Sizes.Length; s++)
            {
                int sz = Sizes[s];
                using (var bmp = new Bitmap(sz * letters.Length, sz, PixelFormat.Format32bppArgb))
                using (var g = Graphics.FromImage(bmp))
                {
                    for (int i = 0; i < letters.Length; i++) Draw(g, i * sz, sz, letters[i], colors[i]);
                    paths[s] = Path.Combine(dir, "strip" + sz + ".png");
                    bmp.Save(paths[s], ImageFormat.Png);
                }
            }
            return paths;
        }

        public static string[] Mains(string dir, string letter, Color color)
        {
            Directory.CreateDirectory(dir);
            var paths = new string[Sizes.Length];
            for (int s = 0; s < Sizes.Length; s++)
            {
                int sz = Sizes[s];
                using (var bmp = new Bitmap(sz, sz, PixelFormat.Format32bppArgb))
                using (var g = Graphics.FromImage(bmp))
                {
                    Draw(g, 0, sz, letter, color);
                    paths[s] = Path.Combine(dir, "main" + sz + ".png");
                    bmp.Save(paths[s], ImageFormat.Png);
                }
            }
            return paths;
        }
    }
}
