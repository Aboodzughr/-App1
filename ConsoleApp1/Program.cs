using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace ConsoleApp1
{
    class Program
    {
        static List<(string, string)> tasks = new List<(string, string)>();

        static void Main()
        {
            while (true)
            {
                Console.WriteLine("-------------");
                Console.WriteLine("1. Add");
                Console.WriteLine("2. View");
                Console.WriteLine("3. Done");
                Console.WriteLine("4. Status");
                Console.WriteLine("5. Exit");
                Console.WriteLine("-------------");
                string choise = Console.ReadLine();

                switch (choise)
                {
                    case "1":
                        Console.Write("Task: ");
                        tasks.Add((Console.ReadLine(), "todo"));
                        break;

                    case "2":
                        for (int i = 0; i < tasks.Count; i++)
                        {
                            Console.WriteLine($"{i + 1}. {tasks[i].Item1} - {tasks[i].Item2}");
                        }

                        break;

                    case "3":
                        Console.Write("Done: ");
                        int doneIndex = int.Parse(Console.ReadLine()) - 1;
                        if (doneIndex >= 0 && doneIndex < tasks.Count)
                        {
                            tasks.RemoveAt(doneIndex);
                        }
                        break;

                    case "4":
                        Console.Write("Task: ");
                        int statusIndex = int.Parse(Console.ReadLine()) - 1;
                        if (statusIndex >= 0 && statusIndex < tasks.Count)
                        {
                            Console.Write("Status (todo, doing, done): ");
                            string newStatus = Console.ReadLine().ToLower();

                            if (newStatus == "todo" || newStatus == "doing" || newStatus == "done")
                            {
                                tasks[statusIndex] = (tasks[statusIndex].Item1, newStatus);
                            }
                            else
                            {
                                Console.WriteLine("Invalid status!");
                            }

                        }
                        else
                        {
                            Console.WriteLine("Not found!");
                        }
                        break;

                    case "5":
                        return;
                }
            }
        }
    }
}
