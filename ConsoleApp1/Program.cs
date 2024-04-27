using System;
using System.Collections.Generic;
using System.Threading.Tasks;

namespace ConsoleApp1
{
    public enum TaskStatus
    {
        Todo,
        Doing,
        Done
    }

    public class TaskManager
    {
        private List<Task> tasks = new List<Task>();

        public void AddTask(string description)
        {
            tasks.Add(new Task(description, TaskStatus.Todo));
        }

        public void ViewTasks()
        {
            for (int i = 0; i < tasks.Count; i++)
            {
                Console.WriteLine($"{i + 1}. - {tasks[i].Status}");
            }
        }

        public void MarkTaskDone(int index)
        {
            if (index >= 0 && index < tasks.Count)
            {
                tasks.RemoveAt(index);
            }
        }

        public void UpdateTaskStatus(int index, TaskStatus newStatus)
        {
            if (index >= 0 && index < tasks.Count)
            {
                tasks[index].Status = newStatus;
            }
        }

        public bool IsValidIndex(int index)
        {
            return index >= 0 && index < tasks.Count;
        }
    }

    class Program
    {
        static TaskManager taskManager = new TaskManager();

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
                string choice = Console.ReadLine();

                switch (choice)
                {
                    case "1":
                        Console.Write("Task: ");
                        taskManager.AddTask(Console.ReadLine());
                        break;

                    case "2":
                        taskManager.ViewTasks();
                        break;

                    case "3":
                        Console.Write("Done : ");
                        int doneIndex = int.Parse(Console.ReadLine()) - 1;
                        if (taskManager.IsValidIndex(doneIndex))
                        {
                            taskManager.MarkTaskDone(doneIndex);
                        }
                        break;

                    case "4":
                        Console.Write("Task : ");
                        int statusIndex = int.Parse(Console.ReadLine()) - 1;
                        if (taskManager.IsValidIndex(statusIndex))
                        {
                            Console.Write("Status (Todo, Doing, Done): ");
                            if (Enum.TryParse<TaskStatus>(Console.ReadLine(), true, out TaskStatus newStatus))
                            {
                                taskManager.UpdateTaskStatus(statusIndex, newStatus);
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
