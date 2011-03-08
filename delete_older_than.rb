#!/usr/bin/ruby

def delete_older(path, age_in_seconds)

  Dir.foreach(path) { |name|

    next if name == '.' or name == '..'
 
    full_name = File.join(path, name)

    case File.ftype(full_name)

    when "file"
      age = Time.now - File.mtime(full_name)

      if age > age_in_seconds
        puts "Deleting file #{full_name}"
        File.unlink(full_name)
      end

    when "directory"
      delete_older(full_name, age_in_seconds)
    #  if (Dir.entries(full_name) - ['.', '..']).empty?
    #    puts "Deleting directory #{full_name}"
    #    Dir.rmdir(full_name)
    #  end
    end

  }
end

path = ARGV.shift or raise "Missing path to delete"
age  = ARGV.shift or raise "Missing age in days"

age_in_seconds = age.to_i * 24*60*60


delete_older(path, age_in_seconds) rescue puts "Error: #$!"
